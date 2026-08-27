"""Fase 6 — a validação do que chega pela ponte.

A regra do Master Loop, aplicada ao pé da letra: a extensão não é fonte
confiável só porque é nossa. Ela roda dentro do navegador, lê um DOM que
ninguém aqui controla, e um serviço pode trocar o player amanhã sem avisar.
"""

from __future__ import annotations

import time

import pytest

from app.bridge.eventos import (
    DERIVA_MAXIMA_SEGUNDOS,
    EventoDeMidia,
    PROTOCOL_VERSION,
    Recusa,
    TIPOS,
    validar,
)


AGORA = 1_780_000_000.0


def mensagem(**payload):
    base = {"sessionId": "sessao-1", "tabId": 7, "windowId": 1}
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "messageType": "POSITION_SYNC",
        "timestamp": AGORA * 1000,
        "payload": {**base, **payload},
    }


def ok(**payload) -> EventoDeMidia:
    resultado = validar(mensagem(**payload), AGORA)
    assert isinstance(resultado, EventoDeMidia), resultado
    return resultado


def recusa(**payload) -> Recusa:
    resultado = validar(mensagem(**payload), AGORA)
    assert isinstance(resultado, Recusa), resultado
    return resultado


# ── Envelope ──────────────────────────────────────────────────────────────


def test_os_oito_eventos_da_fase_6_sao_aceitos():
    """Lista curta de propósito: nada de inventar evento antes de haver
    consumidor do outro lado."""
    assert TIPOS == {
        "SESSION_STARTED", "MEDIA_CHANGED", "PLAY", "PAUSE",
        "SEEK", "ENDED", "POSITION_SYNC", "SESSION_ENDED",
    }
    for tipo in TIPOS:
        bruta = {**mensagem(), "messageType": tipo}
        assert isinstance(validar(bruta, AGORA), EventoDeMidia)


def test_versao_de_protocolo_diferente_e_recusada():
    bruta = {**mensagem(), "protocolVersion": 2}

    assert validar(bruta, AGORA).code == "PROTOCOL_VERSION_MISMATCH"


def test_tipo_desconhecido_e_recusado():
    bruta = {**mensagem(), "messageType": "EPISODE_CHANGED"}

    assert validar(bruta, AGORA).code == "UNKNOWN_MESSAGE_TYPE"


def test_o_que_nao_e_objeto_nao_e_mensagem():
    for lixo in (None, [], "PING", 42):
        assert validar(lixo, AGORA).code == "INVALID_MESSAGE"


# ── sessionId, aba e provider ─────────────────────────────────────────────


def test_sem_session_id_nao_ha_reproducao_para_identificar():
    """É o embrião da PlaybackIdentity da Fase 11. Sem ele não dá para
    distinguir "mesmo episódio retomado" de "próximo episódio" — que é
    exatamente a distinção que falta hoje e produziu o bug do Batman."""
    assert recusa(sessionId=None).code == "INVALID_SESSION_ID"
    assert recusa(sessionId="   ").code == "INVALID_SESSION_ID"
    assert recusa(sessionId="x" * 200).code == "INVALID_SESSION_ID"


def test_tab_id_precisa_ser_inteiro_de_verdade():
    """`True` é `int` em Python. Sem a checagem explícita, um booleano viraria
    a aba número 1."""
    assert recusa(tabId=True).code == "INVALID_TAB_ID"
    assert recusa(tabId="7").code == "INVALID_TAB_ID"
    # Ausente é legítimo: mensagem que não veio de uma aba.
    assert ok(tabId=None).tabId is None


def test_provider_absurdo_e_recusado():
    assert recusa(provider="x" * 300).code == "INVALID_PROVIDER"
    assert ok(provider="primevideo.com").provider == "primevideo.com"


# ── Tempo ─────────────────────────────────────────────────────────────────


def test_marca_de_tempo_no_futuro_e_recusada():
    bruta = {**mensagem(), "timestamp": (AGORA + DERIVA_MAXIMA_SEGUNDOS + 60) * 1000}

    assert validar(bruta, AGORA).code == "INVALID_TIMESTAMP"


def test_relogio_da_aba_ligeiramente_torto_nao_cala_a_ponte():
    """A tolerância é generosa de propósito: recusar por horário torto calaria
    a ponte inteira por um motivo que não tem nada a ver com mídia."""
    bruta = {**mensagem(), "timestamp": (AGORA + 60) * 1000}

    assert isinstance(validar(bruta, AGORA), EventoDeMidia)


def test_sem_marca_de_tempo_utilizavel():
    for valor in (None, "agora", float("nan")):
        bruta = {**mensagem(), "timestamp": valor}
        assert validar(bruta, AGORA).code == "INVALID_TIMESTAMP"


# ── Valores impossíveis ───────────────────────────────────────────────────


def test_posicao_alem_do_fim_e_de_outra_reproducao():
    """O caso que mais rende, e o que enganou o cartão antes.

    A linha do tempo congelada do Chrome publicava a posição de um vídeo
    fechado, e ela CABIA na duração — parecia plausível. Aqui não cabe: estar
    além do fim não é um valor ruim, é um valor de outra coisa.
    """
    assert recusa(currentTime=3000.0, duration=2879.6).code == "IMPOSSIBLE_POSITION"


def test_arredondamento_no_fim_do_video_passa():
    """`currentTime` pode passar de `duration` por frações no último quadro."""
    assert ok(currentTime=2879.8, duration=2879.6).currentTime == 2879.8


def test_duracao_zero_ou_negativa_vira_ausente_sem_derrubar_a_mensagem():
    """Zero não é duração: é ao vivo, ou metadata que não chegou. O resto da
    mensagem continua valendo."""
    evento = ok(duration=0, currentTime=120.0)

    assert evento.duration is None
    assert evento.currentTime == 120.0


def test_posicao_negativa_vira_ausente():
    assert ok(currentTime=-5.0).currentTime is None


def test_nan_e_infinito_nunca_viram_numero():
    """`Infinity` é o que o elemento reporta em transmissão ao vivo, e `NaN`
    antes de a metadata carregar. Nenhum dos dois é duração."""
    assert ok(duration=float("inf")).duration is None
    assert ok(currentTime=float("nan")).currentTime is None


def test_booleano_nunca_vira_tempo():
    """`True` valeria 1.0 sem a checagem — um segundo que ninguém mediu."""
    assert ok(currentTime=True).currentTime is None


def test_velocidade_fora_da_faixa_do_html_vira_ausente():
    """O HTML permite de 0.0625 a 16."""
    assert ok(playbackRate=0.0).playbackRate is None
    assert ok(playbackRate=100.0).playbackRate is None
    assert ok(playbackRate=1.5).playbackRate == 1.5


def test_estado_de_reproducao_desconhecido_e_recusado():
    assert recusa(playbackState="buffering").code == "INVALID_PLAYBACK_STATE"
    assert ok(playbackState="ended").playbackState == "ended"


def test_nada_e_corrigido_em_silencio():
    """Ou passa, ou vira ausente, ou a mensagem é recusada.

    Corrigir valor caladamente é como um número errado entra no sistema
    parecendo certo — que é a história inteira do bug do Batman.
    """
    evento = ok(currentTime=-1.0, duration=-1.0, playbackRate=999.0)

    assert (evento.currentTime, evento.duration, evento.playbackRate) == (None, None, None)


# ── O caminho feliz, com os números reais medidos ─────────────────────────


def test_a_leitura_real_do_prime_video_passa_inteira():
    """Os valores medidos ao vivo em 14/08/2026, Spider-Noir."""
    evento = ok(
        provider="www.primevideo.com",
        playbackState="playing",
        currentTime=1389.945105,
        duration=2879.606,
        playbackRate=1,
        audible=True,
        muted=False,
    )

    assert evento.messageType == "POSITION_SYNC"
    assert evento.currentTime == 1389.945105
    assert evento.duration == 2879.606
    assert evento.playbackState == "playing"
    assert evento.audible is True


def test_o_relogio_de_verdade_tambem_serve():
    """Sanidade: a validação não depende de um instante inventado."""
    agora = time.time()
    bruta = {**mensagem(), "timestamp": agora * 1000}

    assert isinstance(validar(bruta, agora), EventoDeMidia)
