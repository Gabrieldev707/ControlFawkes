"""Fases 11 e 12 — Identidades de mídia e o histórico que as respeita.

O plano escreve o cenário da Fase 11 literalmente:

    Rick and Morty
    S01E01 → S01E02 → S01E03

    PlaybackIdentity muda.
    EPISODE_CHANGED.
    WorkIdentity permanece.
    Uma obra no histórico.

E o gate da Fase 12 proíbe, com todas as letras:

    EPISODE_CHANGED → nova linha automaticamente
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.bridge.estado import EstadoDaPonte
from app.bridge.eventos import validar
from app.history.recorder import HistoryRecorder
from app.history.store import HistoryStore
from app.media.fusao import fundir_com_a_ponte
from app.media.identidade import (
    IdentidadeDaObra,
    IdentidadeDaReproducao,
    identidade_da_reproducao,
)
from app.media.now_playing import NowPlaying


@pytest.fixture
def store(tmp_path) -> HistoryStore:
    return HistoryStore(tmp_path / "historico.json")


def tocando(**overrides: object) -> NowPlaying:
    campos: dict = {
        "title": "Netflix",
        "artist": None,
        "app": "Chrome",
        "platform": "NETFLIX",
        "playing": True,
        "position_seconds": None,
        "duration_seconds": None,
        "thumbnail": None,
        "trustworthy": False,
    }
    campos.update(overrides)
    return NowPlaying(**campos)


def ponte(**payload: object) -> EstadoDaPonte:
    base: dict = {
        "sessionId": "sessao-1",
        "provider": "www.netflix.com",
        "playbackState": "playing",
        "currentTime": 100.0,
        "duration": 1320.0,
    }
    base.update(payload)
    estado = EstadoDaPonte()
    estado.registrar(
        validar(
            {
                "protocolVersion": 1,
                "messageType": "POSITION_SYNC",
                "timestamp": 0.0,
                "payload": base,
            },
            agora=1000.0,
        ),
        agora=0.0,
    )
    return estado


# ── Fase 11: as duas identidades ──────────────────────────────────────────

def test_a_identidade_da_reproducao_prefere_o_sinal_mais_forte():
    """A ordem é: id da página, depois os números, depois nome e duração.

    Misturar os sinais numa chave só faria a MESMA reprodução gerar chaves
    diferentes conforme o que a leitura conseguiu ler naquele segundo — e duas
    chaves para a mesma reprodução é o que faz o histórico achar que trocou de
    episódio e recalibrar a posição sem motivo.
    """
    assert identidade_da_reproducao(page_id="81234567") == "id:81234567"
    assert identidade_da_reproducao(temporada=1, episodio_numero=4) == "s1e4"
    assert identidade_da_reproducao(episodio="Piloto", duracao=1320.0) == "piloto|1320"
    # O mais forte vence mesmo com os outros presentes.
    assert identidade_da_reproducao(
        page_id="81234567", temporada=1, episodio_numero=4, episodio="Piloto",
    ) == "id:81234567"


def test_sem_sinal_nenhum_nao_se_inventa_identidade():
    """Fingir uma chave faria duas reproduções desconhecidas passarem por
    iguais — e aí a posição de uma seria herdada pela outra."""
    assert identidade_da_reproducao() is None


def test_a_identidade_da_obra_nao_muda_entre_episodios():
    """A frase que a Fase 11 existe para escrever."""
    obra = IdentidadeDaObra(titulo="Rick and Morty", platform="NETFLIX")

    episodios = [
        IdentidadeDaReproducao(obra=obra, temporada=1, episodio_numero=numero)
        for numero in (1, 2, 3)
    ]

    # PlaybackIdentity muda.
    assert [e.chave for e in episodios] == ["s1e1", "s1e2", "s1e3"]
    assert len({e.chave for e in episodios}) == 3
    # WorkIdentity permanece.
    assert {e.obra.chave for e in episodios} == {"NETFLIX::rick and morty"}


def test_a_obra_separa_servicos_e_ignora_acento():
    """"O Justiceiro" é filme de 2004 no Max e série da Marvel no Disney+."""
    max_ = IdentidadeDaObra(titulo="O Justiceiro", platform="MAX")
    disney = IdentidadeDaObra(titulo="O Justiceiro", platform="DISNEY_PLUS")

    assert max_.chave != disney.chave
    assert IdentidadeDaObra(titulo="A Casa do Dragão", platform="MAX").chave == (
        "MAX::a casa do dragao"
    )


def test_uma_obra_sem_nome_nao_e_uma_identidade():
    with pytest.raises(ValueError):
        IdentidadeDaObra(titulo="   ", platform="NETFLIX")


# ── Fase 12: o histórico que as respeita ──────────────────────────────────

def _maratonar(gravador: HistoryRecorder, episodios, segundos_por_episodio=200):
    """Assiste uma sequência de episódios, um após o outro."""
    for numero, nome in episodios:
        estado = ponte(
            workTitle="Rick and Morty",
            episodeTitle=nome,
            seasonNumber=1,
            episodeNumber=numero,
            pageId=f"8100000{numero}",
        )
        for _ in range(segundos_por_episodio):
            gravador.observar(
                fundir_com_a_ponte(tocando(), estado, agora=0.0), 1.0, "ASSISTINDO",
            )
    gravador.encerrar()


def test_a_maratona_vira_UMA_obra_no_historico(store: HistoryStore):
    """O cenário literal da Fase 11, e o gate da Fase 12.

    S01E01 → S01E02 → S01E03 e uma obra só. Sem fragmentação por episódio, que
    é a primeira frase do gate.
    """
    _maratonar(HistoryRecorder(store), [(1, "Piloto"), (2, "Lawnmower Dog"), (3, "Anatomy Park")])

    itens = store.listar()
    assert len(itens) == 1
    assert itens[0].titulo == "Rick and Morty"
    assert itens[0].chave == "NETFLIX::rick and morty"


def test_a_maratona_soma_o_tempo_dos_tres(store: HistoryStore):
    """Uma linha, e o tempo dos três episódios dentro dela."""
    _maratonar(HistoryRecorder(store), [(1, "Piloto"), (2, "Lawnmower Dog"), (3, "Anatomy Park")])

    [item] = store.listar()
    assert item.segundos == pytest.approx(600.0, abs=5.0)
    # E a linha se reconhece como multi-reprodução: é série.
    assert item.multiplas_reproducoes is True


def test_o_episodio_atual_e_o_ultimo_visto(store: HistoryStore):
    """"EPISODE_CHANGED deve atualizar episódio" — e o que fica é o último."""
    _maratonar(HistoryRecorder(store), [(1, "Piloto"), (2, "Lawnmower Dog"), (3, "Anatomy Park")])

    [item] = store.listar()
    assert item.como_obra()["episodio"] == "T1 E3"


def test_o_episodio_seguinte_nao_herda_a_posicao_do_anterior(store: HistoryStore):
    """"EPISODE_CHANGED deve resetar/recalibrar posição".

    O bug do Loki ao contrário: sem isto, a posição do episódio que ACABOU
    sobrevive ao seguinte, e a série fica marcada como terminada para sempre.
    """
    gravador = HistoryRecorder(store)

    quase_no_fim = ponte(
        workTitle="Rick and Morty", seasonNumber=1, episodeNumber=1,
        pageId="81000001", currentTime=1300.0, duration=1320.0,
    )
    for _ in range(200):
        gravador.observar(
            fundir_com_a_ponte(tocando(), quase_no_fim, agora=0.0), 1.0, "ASSISTINDO",
        )

    comecando = ponte(
        workTitle="Rick and Morty", seasonNumber=1, episodeNumber=2,
        pageId="81000002", currentTime=15.0, duration=1320.0,
    )
    for _ in range(200):
        gravador.observar(
            fundir_com_a_ponte(tocando(), comecando, agora=0.0), 1.0, "ASSISTINDO",
        )
    gravador.encerrar()

    [item] = store.listar()
    assert item.posicao == pytest.approx(15.0)
    # E a série continua na lista: ela não terminou porque um episódio terminou.
    assert item.terminado is False
    assert [i.titulo for i in store.continuar()] == ["Rick and Morty"]


def test_o_mesmo_episodio_retomado_nao_e_um_episodio_novo(store: HistoryStore):
    """A distinção que a Fase 11 existe para permitir.

    Mesmo `pageId`, posição maior: é a mesma reprodução continuando, e a
    posição AVANÇA em vez de abrir contagem nova.
    """
    gravador = HistoryRecorder(store)

    for posicao in (100.0, 400.0, 900.0):
        estado = ponte(
            workTitle="Rick and Morty", seasonNumber=1, episodeNumber=1,
            pageId="81000001", currentTime=posicao, duration=1320.0,
        )
        for _ in range(100):
            gravador.observar(
                fundir_com_a_ponte(tocando(), estado, agora=0.0), 1.0, "ASSISTINDO",
            )
    gravador.encerrar()

    [item] = store.listar()
    assert item.posicao == pytest.approx(900.0)
    assert item.reproducao == "id:81000001"


def test_serie_diferente_e_linha_diferente(store: HistoryStore):
    gravador = HistoryRecorder(store)
    _maratonar(gravador, [(1, "Piloto")])

    outra = ponte(workTitle="Sherlock", seasonNumber=1, episodeNumber=1, pageId="70000001")
    outro = HistoryRecorder(store)
    for _ in range(200):
        outro.observar(fundir_com_a_ponte(tocando(), outra, agora=0.0), 1.0, "ASSISTINDO")
    outro.encerrar()

    assert sorted(i.titulo for i in store.listar()) == ["Rick and Morty", "Sherlock"]


def test_o_ended_de_um_episodio_nao_marca_o_seguinte(store: HistoryStore):
    """"concluída" pertence à REPRODUÇÃO, não à obra.

    Sem isto, terminar um episódio marcaria a série inteira — e ela sumiria de
    "continuar assistindo" no momento em que a pessoa MAIS quer o próximo.
    """
    gravador = HistoryRecorder(store)

    acabou = ponte(
        workTitle="Rick and Morty", seasonNumber=1, episodeNumber=1,
        pageId="81000001", currentTime=1319.0, duration=1320.0,
    )
    for _ in range(200):
        gravador.observar(
            fundir_com_a_ponte(tocando(), acabou, agora=0.0), 1.0, "ASSISTINDO",
        )
    gravador.observar(
        replace(fundir_com_a_ponte(tocando(), acabou, agora=0.0), ended=True),
        1.0, "ASSISTINDO",
    )

    seguinte = ponte(
        workTitle="Rick and Morty", seasonNumber=1, episodeNumber=2,
        pageId="81000002", currentTime=20.0, duration=1320.0,
    )
    for _ in range(200):
        gravador.observar(
            fundir_com_a_ponte(tocando(), seguinte, agora=0.0), 1.0, "ASSISTINDO",
        )
    gravador.encerrar()

    [item] = store.listar()
    assert item.concluida is False
    assert [i.titulo for i in store.continuar()] == ["Rick and Morty"]


def test_a_extensao_caindo_no_meio_nao_fragmenta(store: HistoryStore):
    """"navegador fechado" e "extensão reconectada", do plano.

    Sem a ponte, a leitura volta a ser a do Windows — que na Netflix não sabe
    nada. O que já foi gravado continua lá, com a obra que se conhecia, e a
    volta da extensão não abre linha nova.
    """
    gravador = HistoryRecorder(store)
    estado = ponte(workTitle="Rick and Morty", seasonNumber=1, episodeNumber=1,
                   pageId="81000001")

    for _ in range(200):
        gravador.observar(
            fundir_com_a_ponte(tocando(), estado, agora=0.0), 1.0, "ASSISTINDO",
        )
    # A extensão cai: nada mais da ponte.
    for _ in range(50):
        gravador.observar(
            fundir_com_a_ponte(tocando(), EstadoDaPonte(), agora=0.0), 1.0, "ASSISTINDO",
        )
    # E volta.
    for _ in range(200):
        gravador.observar(
            fundir_com_a_ponte(tocando(), estado, agora=0.0), 1.0, "ASSISTINDO",
        )
    gravador.encerrar()

    itens = store.listar()
    assert len(itens) == 1
    assert itens[0].titulo == "Rick and Morty"


def test_o_historico_anterior_continua_funcionando(store: HistoryStore):
    """Terceira frase do gate da Fase 12.

    Um serviço sem adapter — que são cinco dos seis — segue pelo caminho de
    sempre: nome do episódio e duração como identidade da reprodução.
    """
    gravador = HistoryRecorder(store)
    leitura = tocando(
        title="Família Soprano", platform="MAX", trustworthy=True,
        episode="Members Only", position_seconds=600.0, duration_seconds=3600.0,
    )

    for _ in range(200):
        gravador.observar(leitura, 1.0, "ASSISTINDO")
    gravador.encerrar()

    [item] = store.listar()
    assert item.titulo == "Família Soprano"
    assert item.reproducao == "members only|3600"
