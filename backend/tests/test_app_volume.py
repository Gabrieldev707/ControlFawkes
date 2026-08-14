import pytest

from app.windows.app_volume import (
    PLATFORM_PROCESSES,
    SCOPE_LABELS,
    AppVolumeUnavailable,
    WindowsAppVolumeAdapter,
)


class FakeVolume:
    def __init__(self, level: float = 0.5, muted: int = 0):
        self.level = level
        self.muted = muted

    def GetMasterVolume(self) -> float:  # noqa: N802 - assinatura da COM
        return self.level

    def SetMasterVolume(self, value: float, _guid) -> None:  # noqa: N802
        self.level = value

    def GetMute(self) -> int:  # noqa: N802
        return self.muted

    def SetMute(self, value: int, _guid) -> None:  # noqa: N802
        self.muted = value


class FakeProcess:
    def __init__(self, name: str):
        self._name = name

    def name(self) -> str:
        return self._name


class FakeSession:
    def __init__(self, name: str | None, volume: FakeVolume | None = None):
        self.Process = FakeProcess(name) if name else None
        self.SimpleAudioVolume = volume or FakeVolume()


def adapter_with(*sessions: FakeSession) -> WindowsAppVolumeAdapter:
    return WindowsAppVolumeAdapter(session_reader=lambda: list(sessions))


def test_reads_the_volume_of_the_platform_process():
    adapter = adapter_with(FakeSession("Spotify.exe", FakeVolume(0.42)))

    state = adapter.get_state("SPOTIFY")

    assert state.level == 42
    assert state.process == "spotify.exe"


def test_sets_only_the_session_of_that_application():
    spotify = FakeVolume(0.5)
    chrome = FakeVolume(0.9)
    adapter = adapter_with(
        FakeSession("Spotify.exe", spotify),
        FakeSession("chrome.exe", chrome),
    )

    adapter.set_level("SPOTIFY", 20)

    assert spotify.level == pytest.approx(0.2)
    # O áudio das outras aplicações não pode ser tocado.
    assert chrome.level == pytest.approx(0.9)


def test_delta_is_clamped_between_zero_and_one_hundred():
    volume = FakeVolume(0.95)
    adapter = adapter_with(FakeSession("chrome.exe", volume))

    assert adapter.change_level("NETFLIX", 20).level == 100

    volume.level = 0.02
    assert adapter.change_level("NETFLIX", -20).level == 0


def test_toggles_mute_and_reads_the_value_back():
    volume = FakeVolume(0.5, muted=0)
    adapter = adapter_with(FakeSession("Spotify.exe", volume))

    assert adapter.toggle_mute("SPOTIFY").muted is True
    assert adapter.toggle_mute("SPOTIFY").muted is False


def test_raises_when_the_application_is_not_playing():
    adapter = adapter_with(FakeSession("chrome.exe"))

    with pytest.raises(AppVolumeUnavailable):
        adapter.get_state("SPOTIFY")


def test_ignores_sessions_without_a_process():
    adapter = adapter_with(FakeSession(None), FakeSession("Spotify.exe", FakeVolume(0.3)))

    assert adapter.get_state("SPOTIFY").level == 30


def test_every_platform_maps_to_a_process_with_a_readable_label():
    for platform, processes in PLATFORM_PROCESSES.items():
        assert processes, platform
        for process in processes:
            assert process in SCOPE_LABELS, f"{platform} -> {process} sem rótulo"


def test_a_service_installed_as_an_app_is_found_in_edge():
    """Serviço "instalado" é um PWA do Edge, não um programa próprio: medido,
    a Netflix instalada aparece como `msedge.exe`. Sem o Edge na lista, mexer
    no volume da Netflix não achava sessão e caía no volume global — abaixava
    o sistema inteiro em vez do filme."""
    from app.windows.app_volume import WindowsAppVolumeAdapter

    class Sessao:
        def __init__(self, nome):
            self.Process = type("P", (), {"name": lambda _self: nome})()
            self.SimpleAudioVolume = type(
                "V", (), {
                    "GetMasterVolume": lambda _self: 0.4,
                    "GetMute": lambda _self: 0,
                },
            )()

    adaptador = WindowsAppVolumeAdapter(session_reader=lambda: [Sessao("msedge.exe")])
    estado = adaptador.get_state("NETFLIX")

    assert estado.process == "msedge.exe"
    assert estado.level == 40
    assert SCOPE_LABELS[estado.process] == "Edge"


def test_chrome_still_wins_when_both_are_playing():
    """A ordem da lista é a preferência: o Chrome é onde as plataformas abrem
    por padrão, então ele vem primeiro."""
    from app.windows.app_volume import WindowsAppVolumeAdapter

    class Sessao:
        def __init__(self, nome):
            self.Process = type("P", (), {"name": lambda _self: nome})()
            self.SimpleAudioVolume = type(
                "V", (), {
                    "GetMasterVolume": lambda _self: 0.5,
                    "GetMute": lambda _self: 0,
                },
            )()

    adaptador = WindowsAppVolumeAdapter(
        session_reader=lambda: [Sessao("msedge.exe"), Sessao("chrome.exe")],
    )

    assert adaptador.get_state("NETFLIX").process == "chrome.exe"
