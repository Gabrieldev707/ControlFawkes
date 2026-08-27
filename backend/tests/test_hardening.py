"""Fase 17 — o que acontece quando as coisas dão errado.

O gate desta fase tem quatro linhas, e todas são sobre NÃO acontecer:

    nenhum crash
    nenhum `currentTime` velho tratado como vivo
    nenhuma sessão fantasma persistente
    o plano B funciona

As três primeiras já custaram caro neste projeto, cada uma de um jeito, e os
testes abaixo estão presos aos episódios reais em vez de a cenários imaginados.

O que este arquivo NÃO repete: os casos já cobertos noutro lugar — enquadramento
inválido e versão de protocolo em `test_bridge_native_host.py`, bfcache em
`video-observer.test.ts`, título genérico em `test_characterization_media.py`.
Duplicar teste não aumenta cobertura; aumenta manutenção.
"""

from __future__ import annotations

import time

import pytest

from app.bridge.estado import (
    SEGUNDOS_ATE_DESCONECTAR,
    SEGUNDOS_ATE_O_TEMPO_ENVELHECER,
    EstadoDaPonte,
)
from app.bridge.eventos import EventoDeMidia, Recusa, validar
from app.media.fusao import fundir_com_a_ponte
from app.media.now_playing import NowPlaying


def mensagem(**payload: object) -> dict:
    base: dict = {
        "sessionId": "aba-1",
        "provider": "www.netflix.com",
        "playbackState": "playing",
        "currentTime": 100.0,
        "duration": 3238.0,
        "tabId": 7,
        "workTitle": "Uma Obra",
    }
    base.update(payload)
    return {
        "protocolVersion": 1,
        "messageType": payload.get("messageType", "POSITION_SYNC"),
        "timestamp": 0.0,
        "payload": base,
    }


def valido(**payload: object) -> EventoDeMidia:
    resultado = validar(mensagem(**payload), agora=1000.0)
    assert isinstance(resultado, EventoDeMidia), resultado
    return resultado


# ── Mensagem fora de ordem ────────────────────────────────────────────────

class TestForaDeOrdem:
    """O content script numera cada mensagem (`seq` em `index.js`), e o backend
    ignorava o número por completo: o campo existia e não era lido por ninguém.

    Sem ele, uma mensagem atrasada sobrescreve uma recente e a posição anda PARA
    TRÁS sem nada ter acontecido na tela. É a mesma família do `currentTime`
    congelado que a Fase 0 documentou: um número plausível descrevendo um
    instante que já passou.
    """

    def test_a_posicao_nao_anda_para_tras(self):
        estado = EstadoDaPonte()
        agora = time.monotonic()
        estado.registrar(valido(seq=5, currentTime=500.0), agora=agora)
        estado.registrar(valido(seq=2, currentTime=100.0), agora=agora)

        assert estado.atual(agora).currentTime == pytest.approx(500.0)

    def test_a_mensagem_atrasada_ainda_conta_como_VIDA(self):
        """A aba falou, ainda que atrasado. Só o conteúdo é que não vale.

        Descartar a mensagem inteira faria a sessão envelhecer e sumir por
        causa de uma reordenação de rede.
        """
        estado = EstadoDaPonte()
        estado.registrar(valido(seq=5, currentTime=500.0), agora=0.0)
        estado.registrar(valido(seq=2, currentTime=100.0), agora=30.0)

        viva = estado.atual(agora=30.0)
        assert viva is not None
        assert viva.visto_em == pytest.approx(30.0)

    def test_a_sequencia_seguinte_passa(self):
        estado = EstadoDaPonte()
        agora = time.monotonic()
        estado.registrar(valido(seq=5, currentTime=500.0), agora=agora)
        estado.registrar(valido(seq=6, currentTime=510.0), agora=agora)

        assert estado.atual(agora).currentTime == pytest.approx(510.0)

    def test_a_MESMA_sequencia_passa(self):
        """Igual não é fora de ordem: é reenvio, e reenviar o mesmo estado é
        inofensivo. Recusar aqui descartaria retransmissão legítima."""
        estado = EstadoDaPonte()
        agora = time.monotonic()
        estado.registrar(valido(seq=5, currentTime=500.0), agora=agora)
        estado.registrar(valido(seq=5, currentTime=505.0), agora=agora)

        assert estado.atual(agora).currentTime == pytest.approx(505.0)

    def test_sem_seq_nada_muda(self):
        """Um cliente antigo que não numere continua funcionando."""
        estado = EstadoDaPonte()
        agora = time.monotonic()
        estado.registrar(valido(currentTime=500.0), agora=agora)
        estado.registrar(valido(currentTime=100.0), agora=agora)

        assert estado.atual(agora).currentTime == pytest.approx(100.0)

    def test_sequencias_de_ABAS_diferentes_nao_se_comparam(self):
        """Cada aba tem o seu contador. Comparar entre abas não significa nada."""
        estado = EstadoDaPonte()
        agora = time.monotonic()
        estado.registrar(valido(sessionId="a", seq=90, currentTime=900.0), agora=agora)
        # Duração diferente de propósito: mesmo serviço com a MESMA duração é
        # a mesma reprodução para `_esquecer_fantasmas`, e as duas seriam
        # fundidas por outro motivo — o teste estaria medindo aquilo, não isto.
        estado.registrar(
            valido(sessionId="b", tabId=8, seq=1, currentTime=10.0, duration=1200.0),
            agora=agora,
        )

        assert len(estado.vivas(agora)) == 2
        # E a de sequência BAIXA não foi descartada por causa da outra.
        assert {s.currentTime for s in estado.vivas(agora)} == {900.0, 10.0}


# ── Mensagem duplicada ────────────────────────────────────────────────────

def test_a_mensagem_duplicada_nao_vira_duas_sessoes():
    estado = EstadoDaPonte()
    agora = time.monotonic()
    for _ in range(5):
        estado.registrar(valido(seq=1, currentTime=100.0), agora=agora)

    assert len(estado.vivas(agora)) == 1


# ── Nenhum `currentTime` velho tratado como vivo ──────────────────────────

class TestTempoVelho:
    def test_a_ponte_calada_perde_o_tempo_e_mantem_o_NOME(self):
        """A assimetria da Fase 8: um `currentTime` de dois minutos atrás está
        errado agora; o nome da obra de dois minutos atrás continua certo."""
        estado = EstadoDaPonte()
        estado.registrar(valido(), agora=0.0)

        leitura = estado.leitura(agora=SEGUNDOS_ATE_O_TEMPO_ENVELHECER + 1.0)

        assert leitura is not None
        assert leitura.dinamicos_frescos is False

    def test_a_sessao_que_para_de_falar_some(self):
        estado = EstadoDaPonte()
        estado.registrar(valido(), agora=0.0)

        assert estado.vivas(agora=SEGUNDOS_ATE_DESCONECTAR + 1.0) == []

    def test_pausado_nao_extrapola(self):
        """O tempo passa, o filme não."""
        estado = EstadoDaPonte()
        estado.registrar(valido(playbackState="paused", currentTime=100.0), agora=0.0)

        assert estado.atual(agora=60.0).posicao_agora(60.0) == pytest.approx(100.0)


# ── Nenhuma sessão fantasma persistente ───────────────────────────────────

class TestSemFantasma:
    def test_a_aba_que_avisa_que_saiu_some_na_hora(self):
        """O silêncio EXPLICADO é melhor do que o silêncio medido."""
        estado = EstadoDaPonte()
        estado.registrar(valido(), agora=0.0)
        estado.registrar(valido(messageType="SESSION_ENDED"), agora=1.0)

        assert estado.vivas(agora=1.0) == []

    def test_a_mesma_aba_nao_acumula_sessoes(self):
        """Medido em 26/08/2026: 1078 de 1526 observações tinham sessões
        repetidas na mesma aba, e uma aba chegou a ter OITO."""
        estado = EstadoDaPonte()
        agora = time.monotonic()
        for numero in range(8):
            estado.registrar(
                valido(sessionId=f"s{numero}", tabId=7, seq=numero), agora=agora,
            )

        assert len(estado.vivas(agora)) == 1

    def test_o_navegador_fechado_esvazia_tudo(self):
        """Chrome reiniciado: ninguém fala mais, e o prazo limpa sozinho."""
        estado = EstadoDaPonte()
        agora = time.monotonic()
        for numero in range(4):
            estado.registrar(valido(sessionId=f"s{numero}", tabId=numero), agora=agora)

        assert estado.vivas(agora + SEGUNDOS_ATE_DESCONECTAR + 1.0) == []
        assert estado.saude(agora + SEGUNDOS_ATE_DESCONECTAR + 1.0).connected is False


# ── O plano B funciona ────────────────────────────────────────────────────

class TestFallback:
    def test_sem_ponte_a_leitura_do_windows_atravessa_intacta(self):
        """Quem não instalou a extensão continua com o controle que sempre teve.

        É o caminho que garante que nenhuma fase da ponte regride Spotify, Max,
        Disney+, Prime Video nem YouTube.
        """
        do_windows = NowPlaying(
            title="Duna", artist=None, app="Chrome", platform="MAX",
            playing=True, position_seconds=300.0, duration_seconds=9000.0,
            thumbnail=None, trustworthy=True,
        )

        assert fundir_com_a_ponte(do_windows, EstadoDaPonte()) is do_windows

    def test_a_ponte_caida_devolve_a_leitura_do_windows(self):
        """A extensão parou de falar. A SMTC assume de volta."""
        estado = EstadoDaPonte()
        estado.registrar(valido(), agora=0.0)
        do_windows = NowPlaying(
            title="Duna", artist=None, app="Chrome", platform="MAX",
            playing=True, position_seconds=300.0, duration_seconds=9000.0,
            thumbnail=None, trustworthy=True,
        )

        lida = fundir_com_a_ponte(
            do_windows, estado, agora=SEGUNDOS_ATE_DESCONECTAR + 1.0,
        )

        assert lida.title == "Duna"
        assert lida.position_seconds == pytest.approx(300.0)

    def test_sem_windows_e_sem_ponte_nao_ha_cartao(self):
        assert fundir_com_a_ponte(None, EstadoDaPonte()) is None


# ── Nenhum crash: entrada hostil ──────────────────────────────────────────

class TestEntradaHostil:
    @pytest.mark.parametrize("corpo", [
        None, [], "texto", 42, {"protocolVersion": 1},
        {"protocolVersion": 99, "messageType": "PLAY", "timestamp": 0, "payload": {}},
        {"protocolVersion": 1, "messageType": "INVENTADO", "timestamp": 0, "payload": {}},
        {"protocolVersion": 1, "messageType": "PLAY", "timestamp": 0, "payload": None},
        {"protocolVersion": 1, "messageType": "PLAY", "timestamp": "agora", "payload": {}},
    ])
    def test_lixo_vira_recusa_com_motivo_e_nao_excecao(self, corpo):
        resultado = validar(corpo, agora=1000.0)

        assert isinstance(resultado, Recusa)
        assert resultado.code and resultado.detail

    def test_um_DOM_hostil_nao_derruba_nada(self):
        """`textContent` de um documento inteiro chegando como nome de obra.

        Corta em vez de recusar: o resto da mensagem continua valendo, e um
        nome truncado ainda é melhor do que nenhum.
        """
        evento = valido(workTitle="x" * 5000)

        assert len(evento.workTitle) <= 300

    def test_numeros_impossiveis_viram_ausentes_e_nao_erro(self):
        evento = valido(duration=0.0, playbackRate=999.0)

        assert evento.duration is None
        assert evento.playbackRate is None

    def test_seq_absurdo_nao_derruba(self):
        assert valido(seq=-1).seq is None
        assert valido(seq="dois").seq is None
        assert valido(seq=True).seq is None
        # E um número grande é legítimo: a aba conta sem limite enquanto viver.
        assert valido(seq=10_000_000).seq == 10_000_000
