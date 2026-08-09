"""Volume por aplicativo, via sessões de áudio do Windows.

O volume global mexe no sistema inteiro: abaixar o Spotify abaixava também o
alerta do sistema e qualquer chamada. A Core Audio expõe uma sessão por
processo que está tocando, e é nela que mexemos quando dá.

Limitação real, não escondida: o Chrome agrupa o áudio de todas as abas numa
sessão só. Não há como separar "volume da Netflix" de "volume do YouTube" se as
duas estiverem abertas no mesmo navegador — o que se controla é o áudio do
Chrome. Por isso a resposta sempre diz em que escopo a mudança aconteceu.
"""

from collections.abc import Callable
from dataclasses import dataclass
import sys
from typing import Literal, TypeAlias

from app.schemas.ws import Platform


VolumeScope: TypeAlias = Literal["LOCAL", "GLOBAL"]

# Processo que toca o áudio de cada plataforma. As plataformas de navegador
# compartilham o processo do Chrome — ver a nota do módulo.
PLATFORM_PROCESSES: dict[Platform, tuple[str, ...]] = {
    "SPOTIFY": ("spotify.exe",),
    "YOUTUBE": ("chrome.exe",),
    "NETFLIX": ("chrome.exe",),
    "PRIME_VIDEO": ("chrome.exe",),
    "MAX": ("chrome.exe",),
    "DISNEY_PLUS": ("chrome.exe",),
}

# Nome amigável do que foi realmente afetado, para o feedback não mentir.
SCOPE_LABELS: dict[str, str] = {
    "spotify.exe": "Spotify",
    "chrome.exe": "Chrome",
}


@dataclass(frozen=True)
class AppVolumeState:
    level: int
    muted: bool
    process: str


class AppVolumeUnavailable(RuntimeError):
    """Não há sessão de áudio utilizável para o processo pedido."""


SessionReader = Callable[[], list]


def _read_sessions() -> list:
    if sys.platform != "win32":
        raise AppVolumeUnavailable("Sessões de áudio só existem no Windows")
    try:
        import pythoncom
        from pycaw.pycaw import AudioUtilities
    except ImportError as error:
        raise AppVolumeUnavailable("Dependências de áudio indisponíveis") from error

    pythoncom.CoInitialize()
    try:
        return list(AudioUtilities.GetAllSessions())
    finally:
        pythoncom.CoUninitialize()


class WindowsAppVolumeAdapter:
    def __init__(self, session_reader: SessionReader | None = None) -> None:
        self._session_reader = session_reader or _read_sessions

    def _session_for(self, process_names: tuple[str, ...]):
        wanted = {name.lower() for name in process_names}
        for session in self._session_reader():
            process = getattr(session, "Process", None)
            if process is None:
                continue
            try:
                name = process.name().lower()
            except Exception:  # noqa: BLE001 - processo pode morrer no meio
                continue
            if name in wanted:
                return session, name
        raise AppVolumeUnavailable("Nenhuma sessão de áudio para o aplicativo")

    def get_state(self, platform: Platform) -> AppVolumeState:
        session, name = self._session_for(PLATFORM_PROCESSES[platform])
        volume = session.SimpleAudioVolume
        return AppVolumeState(
            level=self._clamp(round(volume.GetMasterVolume() * 100)),
            muted=bool(volume.GetMute()),
            process=name,
        )

    def set_level(self, platform: Platform, level: int) -> AppVolumeState:
        session, name = self._session_for(PLATFORM_PROCESSES[platform])
        volume = session.SimpleAudioVolume
        volume.SetMasterVolume(self._clamp(level) / 100, None)
        return self._read_back(volume, name)

    def change_level(self, platform: Platform, delta: int) -> AppVolumeState:
        session, name = self._session_for(PLATFORM_PROCESSES[platform])
        volume = session.SimpleAudioVolume
        current = round(volume.GetMasterVolume() * 100)
        volume.SetMasterVolume(self._clamp(current + delta) / 100, None)
        return self._read_back(volume, name)

    def toggle_mute(self, platform: Platform) -> AppVolumeState:
        session, name = self._session_for(PLATFORM_PROCESSES[platform])
        volume = session.SimpleAudioVolume
        volume.SetMute(0 if volume.GetMute() else 1, None)
        return self._read_back(volume, name)

    def _read_back(self, volume, name: str) -> AppVolumeState:
        # Relê do endpoint em vez de confiar no valor enviado: o feedback só
        # pode afirmar o que o Windows confirmou.
        return AppVolumeState(
            level=self._clamp(round(volume.GetMasterVolume() * 100)),
            muted=bool(volume.GetMute()),
            process=name,
        )

    @staticmethod
    def _clamp(level: int) -> int:
        return max(0, min(100, int(level)))
