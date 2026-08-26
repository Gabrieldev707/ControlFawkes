"""Fase 13 — RelogioDaMidia com a ponte no caminho.

Gate:

    Nenhum buraco de posição.
    Nenhuma dupla estimativa.
    Fonte real saudável sempre vence.

As três frases são sobre a mesma coisa: quem tem o direito de dizer onde a
reprodução está, e o que acontece quando essa fonte cala.
"""

from __future__ import annotations

import pytest

from app.bridge.estado import (
    SEGUNDOS_ATE_O_TEMPO_ENVELHECER,
    EstadoDaPonte,
)
from app.bridge.eventos import validar
from app.media.fusao import fundir_com_a_ponte
from app.media.now_playing import NowPlaying


def evento(agora: float, estado: EstadoDaPonte, **payload: object) -> None:
    base: dict = {
        "sessionId": "sessao-1",
        "provider": "www.netflix.com",
        "playbackState": "playing",
        "currentTime": 100.0,
        "duration": 3238.0,
    }
    base.update(payload)
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
        agora=agora,
    )


def netflix(**overrides: object) -> NowPlaying:
    """A leitura do Windows na Netflix: sem posição, porque nunca houve."""
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


# ── Fonte real saudável sempre vence ──────────────────────────────────────

def test_a_posicao_medida_vence_a_estimada():
    """A ponte mede dentro da página; a SMTC publica um instantâneo velho."""
    estado = EstadoDaPonte()
    evento(0.0, estado, currentTime=2974.0)

    fundida = fundir_com_a_ponte(
        netflix(position_seconds=391.0, duration_seconds=3238.0), estado, agora=0.0,
    )

    assert fundida.position_seconds == pytest.approx(2974.0)
    assert fundida.position_stale is False


def test_nao_se_estima_o_que_foi_medido_agora():
    """"não estimar desnecessariamente".

    Zero segundos desde o batimento: a posição é a medida, sem projeção
    nenhuma somada por cima.
    """
    estado = EstadoDaPonte()
    evento(0.0, estado, currentTime=1500.0)

    fundida = fundir_com_a_ponte(netflix(), estado, agora=0.0)

    assert fundida.position_seconds == pytest.approx(1500.0)


def test_entre_batimentos_projeta_uma_vez_so():
    """"Nenhuma dupla estimativa".

    Sete segundos depois do batimento, a posição andou exatamente sete — e não
    catorze, que é o que sairia de duas fontes projetando sobre o mesmo número.
    """
    estado = EstadoDaPonte()
    evento(0.0, estado, currentTime=1500.0)

    fundida = fundir_com_a_ponte(
        netflix(position_seconds=1500.0, duration_seconds=3238.0), estado, agora=7.0,
    )

    assert fundida.position_seconds == pytest.approx(1507.0)


# ── Nenhum buraco de posição ──────────────────────────────────────────────

def test_a_extensao_caindo_nao_apaga_a_posicao():
    """A frase literal do gate, no caso que mais dói.

    Na Netflix a SMTC nunca teve posição. Quando a ponte envelhece, não há
    ninguém para assumir — e sem esta rede a barra sumiria inteira no meio do
    filme, que é a "sensação de cartaz" que este trabalho começou consertando.
    """
    estado = EstadoDaPonte()
    evento(0.0, estado, currentTime=1500.0)

    fundida = fundir_com_a_ponte(
        netflix(), estado, agora=SEGUNDOS_ATE_O_TEMPO_ENVELHECER + 5,
    )

    assert fundida.position_seconds == pytest.approx(1500.0)
    # E o número não avança sozinho: ele é bom, o relógio dele é que parou.
    assert fundida.position_stale is True


def test_a_posicao_parada_nao_e_projetada():
    """Projetar aqui inventaria um avanço que ninguém mediu.

    Duas leituras muito distantes devolvem o MESMO número — se ele andasse, a
    barra passaria do fim do filme sem nada ter acontecido.
    """
    estado = EstadoDaPonte()
    evento(0.0, estado, currentTime=1500.0)

    # Depois do prazo de frescor, e bem depois: o número não pode andar.
    uma = fundir_com_a_ponte(netflix(), estado, agora=SEGUNDOS_ATE_O_TEMPO_ENVELHECER + 5)
    outra = fundir_com_a_ponte(netflix(), estado, agora=SEGUNDOS_ATE_O_TEMPO_ENVELHECER + 60)

    assert uma.position_seconds == outra.position_seconds == pytest.approx(1500.0)


def test_a_smtc_saudavel_assume_quando_a_ponte_envelhece():
    """"avaliar outras fontes" antes do fallback.

    Onde a SMTC TEM posição — Prime Video, Disney+, Max —, é ela quem assume, e
    não o último valor guardado da ponte. Fonte viva vence número parado.
    """
    estado = EstadoDaPonte()
    evento(0.0, estado, currentTime=1500.0, provider="www.primevideo.com")

    fundida = fundir_com_a_ponte(
        netflix(platform="PRIME_VIDEO", title="Invincible", trustworthy=True,
                position_seconds=800.0, duration_seconds=3238.0),
        estado,
        agora=SEGUNDOS_ATE_O_TEMPO_ENVELHECER + 5,
    )

    assert fundida.position_seconds == pytest.approx(800.0)
    assert fundida.position_stale is False


def test_a_extensao_voltando_recalibra():
    """"extensão volta / posição recalibra", e sem salto absurdo.

    O número novo é o medido, não uma continuação do que estava congelado.
    """
    estado = EstadoDaPonte()
    evento(0.0, estado, currentTime=1500.0)

    envelheceu = SEGUNDOS_ATE_O_TEMPO_ENVELHECER + 10
    parada = fundir_com_a_ponte(netflix(), estado, agora=envelheceu)
    assert parada.position_stale is True

    # A extensão volta e diz onde a reprodução de fato está.
    evento(envelheceu, estado, currentTime=1560.0)
    voltou = fundir_com_a_ponte(netflix(), estado, agora=envelheceu)

    assert voltou.position_seconds == pytest.approx(1560.0)
    assert voltou.position_stale is False
    # E o salto é o tempo que passou, não um número inventado.
    assert voltou.position_seconds - parada.position_seconds == pytest.approx(60.0)


def test_a_duracao_tambem_sobrevive_a_queda():
    """Sem duração não há barra, e sem barra o buraco continua existindo."""
    estado = EstadoDaPonte()
    evento(0.0, estado, currentTime=1500.0, duration=3238.0)

    fundida = fundir_com_a_ponte(
        netflix(), estado, agora=SEGUNDOS_ATE_O_TEMPO_ENVELHECER + 5,
    )

    assert fundida.duration_seconds == pytest.approx(3238.0)


def test_sem_ponte_nenhuma_nada_e_inventado():
    """O par: a rede só vale para quem a ponte já mediu.

    Sem extensão instalada, a Netflix continua sem posição — e dizer um número
    aqui seria inventá-lo do nada.
    """
    fundida = fundir_com_a_ponte(netflix(), EstadoDaPonte(), agora=0.0)

    assert fundida.position_seconds is None
