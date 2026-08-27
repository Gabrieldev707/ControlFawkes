"""A temporada chegando ao HISTÓRICO, e não só ao cartão.

Ela era acrescentada na montagem da mensagem, depois de o gravador já ter
recebido a leitura crua. Resultado: o cartão dizia "T1 E1 · Pilot" e "continuar
assistindo" dizia "E1 · Pilot" — a mesma leitura contando duas histórias
diferentes conforme a tela.

E o lookup vale para TODO serviço, não só o que tem adapter:

    Netflix                 publica "E1" — falta a temporada
    Max, Prime, Disney+     publicam só o NOME do episódio, sem número nenhum

O nome isola a linha na série, e achada a linha os dois números vêm juntos.
"""

from __future__ import annotations

import asyncio

import pytest

from app.history.recorder import HistoryRecorder
from app.history.store import HistoryStore
from app.media.now_playing import NowPlaying
from app.protocol.dispatcher import Dispatcher
from app.windows.focus import WindowFocuser


@pytest.fixture
def store(tmp_path) -> HistoryStore:
    return HistoryStore(tmp_path / "historico.json")


class CatalogoQueSabeASerie:
    """O catálogo respondendo o que a API real respondeu, medido."""

    enabled = True

    def __init__(self, resposta: tuple[int, int] | None = (5, 14)) -> None:
        self.resposta = resposta
        self.perguntas: list[tuple] = []

    async def numeros_do_episodio(self, serie, nome=None, numero=None, duracao=None):
        self.perguntas.append((serie, nome, numero, duracao))
        return self.resposta


def tocando(**overrides: object) -> NowPlaying:
    campos: dict = {
        "title": "Breaking Bad",
        "artist": None,
        "app": "Chrome",
        "platform": "MAX",
        "playing": True,
        "position_seconds": 100.0,
        "duration_seconds": 2880.0,
        "thumbnail": None,
        "trustworthy": True,
        "episode": "Ozymandias",
    }
    campos.update(overrides)
    return NowPlaying(**campos)


def dispatcher_com(catalog, store: HistoryStore) -> Dispatcher:
    return Dispatcher(
        catalog=catalog,
        history_recorder=HistoryRecorder(store),
        window_focuser=WindowFocuser(window_lister=lambda: []),
    )


async def _assentar() -> None:
    """Deixa a tarefa de segundo plano terminar."""
    for _ in range(5):
        await asyncio.sleep(0)


# ── O lookup vale para quem NÃO tem adapter ───────────────────────────────

def test_o_max_ganha_temporada_pelo_nome_do_episodio(store: HistoryStore):
    """O Max publica "Ozymandias" e número nenhum.

    O catálogo acha essa linha na série e devolve as duas coisas.
    """
    catalogo = CatalogoQueSabeASerie((5, 14))
    d = dispatcher_com(catalogo, store)

    async def rodar():
        # A primeira volta dispara a busca; a resposta chega para a seguinte.
        d._com_temporada(tocando())
        await _assentar()
        return d._com_temporada(tocando())

    depois = asyncio.run(rodar())

    assert depois.episode == "T5 E14 · Ozymandias"
    # E foi perguntado pelo NOME, que é tudo o que o Max publica.
    assert catalogo.perguntas[0][1] == "Ozymandias"


def test_o_que_o_catalogo_nao_isola_fica_como_estava(store: HistoryStore):
    """A recusa é o que separa isto de um palpite."""
    d = dispatcher_com(CatalogoQueSabeASerie(None), store)

    async def rodar():
        d._com_temporada(tocando())
        await _assentar()
        return d._com_temporada(tocando())

    assert asyncio.run(rodar()).episode == "Ozymandias"


def test_a_temporada_publicada_pelo_servico_nao_e_reconsultada(store: HistoryStore):
    """Quem já disse a temporada não precisa que ninguém a descubra."""
    from app.bridge.estado import EstadoDaPonte
    from app.bridge.eventos import validar

    estado = EstadoDaPonte()
    estado.registrar(
        validar({
            "protocolVersion": 1, "messageType": "POSITION_SYNC", "timestamp": 0.0,
            "payload": {
                "sessionId": "s", "provider": "www.netflix.com",
                "playbackState": "playing", "currentTime": 10.0, "duration": 2880.0,
                "workTitle": "Breaking Bad", "seasonNumber": 5, "episodeNumber": 14,
            },
        }, 1000.0),
        agora=0.0,
    )
    catalogo = CatalogoQueSabeASerie((1, 1))
    d = Dispatcher(
        catalog=catalogo,
        history_recorder=HistoryRecorder(store),
        window_focuser=WindowFocuser(window_lister=lambda: []),
        bridge_state=estado,
    )

    d._com_temporada(tocando(platform="NETFLIX", episode="T5 E14"))

    assert catalogo.perguntas == []


def test_sem_obra_confiavel_nao_se_procura_serie(store: HistoryStore):
    """Um nome que não é o da obra não acha série nenhuma — e procurar por ele
    gastaria seis requisições para errar."""
    catalogo = CatalogoQueSabeASerie((1, 1))
    d = dispatcher_com(catalogo, store)

    d._com_temporada(tocando(trustworthy=False))

    assert catalogo.perguntas == []


# ── O histórico recebe o mesmo que o cartão ───────────────────────────────

def test_continuar_assistindo_recebe_a_temporada(store: HistoryStore):
    """O conserto: o gravador recebia a leitura crua.

    O cartão dizia "T5 E14 · Ozymandias" e o perfil dizia "Ozymandias".
    """
    d = dispatcher_com(CatalogoQueSabeASerie((5, 14)), store)

    async def rodar():
        d._com_temporada(tocando())
        await _assentar()
        for _ in range(400):
            enriquecida = d._com_temporada(tocando())
            d.history_recorder.observar(enriquecida, 1.0, "ASSISTINDO")
        d.history_recorder.encerrar()

    asyncio.run(rodar())

    [item] = store.listar()
    assert item.episodio == "T5 E14 · Ozymandias"
    # E a tela de perfil lê a forma curta de volta.
    assert item.como_obra()["episodio"] == "T5 E14"


def test_o_rotulo_nao_repete_o_que_ja_disse(store: HistoryStore):
    """Na Netflix o "nome" do episódio pode ser o próprio "E1".

    Escrever "T1 E1 · E1" diria a mesma coisa duas vezes.
    """
    d = dispatcher_com(CatalogoQueSabeASerie((1, 1)), store)

    async def rodar():
        d._com_temporada(tocando(episode="E1"))
        await _assentar()
        return d._com_temporada(tocando(episode="E1"))

    assert asyncio.run(rodar()).episode == "T1 E1"


def test_a_consulta_acontece_uma_vez_por_episodio(store: HistoryStore):
    """Seis requisições por consulta, e o laço roda uma vez por segundo."""
    catalogo = CatalogoQueSabeASerie((5, 14))
    d = dispatcher_com(catalogo, store)

    async def rodar():
        for _ in range(50):
            d._com_temporada(tocando())
            await _assentar()

    asyncio.run(rodar())

    assert len(catalogo.perguntas) == 1
