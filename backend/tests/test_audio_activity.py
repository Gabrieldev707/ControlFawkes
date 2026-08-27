"""Está saindo som deste aplicativo agora?

Sem a API de mídia do Windows, a janela aberta era tratada como "tocando" para
sempre. Medido nesta máquina: o Chrome com a sessão de áudio em `Inactive` —
nenhum som saindo — e "Batman: Caped Crusader" somando um segundo por segundo
até 129 minutos no catálogo.
"""

import pytest

from app.media.now_playing import da_janela


class _Processo:
    def __init__(self, nome: str) -> None:
        self._nome = nome

    def name(self) -> str:
        return self._nome


class _Sessao:
    def __init__(self, nome: str, estado: int) -> None:
        self.Process = _Processo(nome)
        self.State = estado


class _AudioUtilitiesFalso:
    def __init__(self, sessoes) -> None:
        self._sessoes = [_Sessao(nome, estado) for nome, estado in sessoes]

    def GetAllSessions(self):  # noqa: N802 - o nome é o da API do pycaw
        return self._sessoes


def _com_sessoes(monkeypatch, sessoes) -> None:
    """Troca a fonte de sessões de áudio do Windows por uma de mentira.

    A função lê `AudioUtilities` do módulo na hora da chamada, então trocar o
    atributo do módulo basta.
    """
    pycaw = pytest.importorskip("pycaw.pycaw")
    monkeypatch.setattr(pycaw, "AudioUtilities", _AudioUtilitiesFalso(sessoes))


# ── O enum do Core Audio ──────────────────────────────────────────────────
#
# Estes três testes existem porque a constante estava errada e NADA pegava: os
# testes de baixo passam o booleano já pronto para `da_janela`, então a função
# que lê o enum de verdade não tinha teste nenhum. O defeito só apareceu
# medindo a máquina com o Disney+ tocando.


def test_an_active_session_is_the_one_that_is_playing(monkeypatch):
    """`Active` é 1. A constante estava em 2, que é `Expired` — sessão morta.

    Medido ao vivo: `chrome.exe` em State=1 com o Disney+ reproduzindo, e a
    função respondendo False. Com a SMTC travada é esta função que decide se
    há reprodução, então tudo no navegador era contado como pausado e uma série
    inteira não virava um segundo de histórico.
    """
    from app.windows.audio_activity import processo_esta_tocando

    _com_sessoes(monkeypatch, [("chrome.exe", 1)])

    assert processo_esta_tocando("chrome.exe") is True


def test_an_inactive_session_is_silence(monkeypatch):
    from app.windows.audio_activity import processo_esta_tocando

    _com_sessoes(monkeypatch, [("chrome.exe", 0)])

    assert processo_esta_tocando("chrome.exe") is False


def test_an_expired_session_is_not_playing_either(monkeypatch):
    """`Expired` é a sessão que morreu — o valor que a constante tinha por
    engano. Se ele voltar a contar como "tocando", este teste cai."""
    from app.windows.audio_activity import processo_esta_tocando

    _com_sessoes(monkeypatch, [("chrome.exe", 2)])

    assert processo_esta_tocando("chrome.exe") is False


def test_another_app_playing_says_nothing_about_this_one(monkeypatch):
    from app.windows.audio_activity import processo_esta_tocando

    _com_sessoes(monkeypatch, [("spotify.exe", 1)])

    assert processo_esta_tocando("chrome.exe") is False


def test_a_silent_window_is_not_playing():
    atual = da_janela(
        "Prime Video: Batman: Caped Crusader - Google Chrome",
        "PRIME_VIDEO",
        tocando=False,
    )

    assert atual is not None
    assert atual.playing is False


def test_a_window_with_sound_is_playing():
    atual = da_janela(
        "Prime Video: Batman: Caped Crusader - Google Chrome",
        "PRIME_VIDEO",
        tocando=True,
    )

    assert atual.playing is True


def test_not_knowing_keeps_the_optimistic_guess():
    """Sem forma de medir, um controle que diz "pausado" para quem está
    assistindo é pior do que um que conta tempo demais."""
    atual = da_janela(
        "Prime Video: Batman: Caped Crusader - Google Chrome",
        "PRIME_VIDEO",
        tocando=None,
    )

    assert atual.playing is True


def test_a_paused_window_never_becomes_watched_time(tmp_path):
    """O gravador já não acumula quando está pausado — o que faltava era
    alguém dizer a verdade sobre estar pausado."""
    from app.history.recorder import SEGUNDOS_ENTRE_GRAVACOES, HistoryRecorder
    from app.history.store import HistoryStore

    store = HistoryStore(tmp_path / "historico.json")
    gravador = HistoryRecorder(store)
    parado = da_janela(
        "Prime Video: Batman: Caped Crusader - Google Chrome",
        "PRIME_VIDEO",
        tocando=False,
    )

    for _ in range(50):
        gravador.observar(parado, SEGUNDOS_ENTRE_GRAVACOES)
    gravador.encerrar()

    assert store.listar() == []


@pytest.mark.parametrize("nome", [None, ""])
def test_without_a_process_name_there_is_nothing_to_measure(nome):
    from app.windows.audio_activity import processo_esta_tocando

    assert processo_esta_tocando(nome) is None
