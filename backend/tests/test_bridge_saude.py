"""Fase 3 — saúde das fontes, com a assimetria preservada.

O gate desta fase é "mesmos inputs → mesmos outputs". Por isso a instrumentação
só OBSERVA: nenhuma decisão da `LeituraEmVoo` passou a depender dela, e os
characterization tests da Fase 0 continuam sendo a prova de que nada mudou.
"""

from __future__ import annotations

import asyncio

import pytest

from app.bridge.saude import SaudeDaSMTC, SaudeDoWindowTitle
from app.media.now_playing import LeituraEmVoo


# ── Window Title: presença, nunca "healthy" ───────────────────────────────


def test_o_window_title_nao_tem_healthy_generico():
    """Critério de implementação incorreta nº 16.

    Ele SEMPRE devolve um título; o modo de falha dele é estar errado em
    silêncio. Um `healthy=true` faria "Netflix - Home - Netflix" passar por
    dado fresco enquanto um filme roda.
    """
    campos = set(SaudeDoWindowTitle.__dataclass_fields__)

    assert campos == {"windowPresent", "titlePresent", "parseable"}
    assert "healthy" not in campos
    assert "lastSeen" not in campos


def test_sem_janela_e_diferente_de_janela_sem_titulo():
    sem_janela = SaudeDoWindowTitle.de(None)
    sem_titulo = SaudeDoWindowTitle.de("   ")

    assert sem_janela.windowPresent is False
    assert sem_titulo.windowPresent is True
    assert sem_titulo.titlePresent is False


def test_titulo_de_obra_e_parseavel():
    saude = SaudeDoWindowTitle.de("O Justiceiro | Disney+ - Google Chrome")

    assert saude == SaudeDoWindowTitle(True, True, True)


def test_a_home_do_servico_tambem_e_parseavel():
    """`parseable` é presença, não verdade.

    "Netflix - Home - Netflix" limpa para "Home", que É um nome — só não é o
    de uma obra. Quem sabe disso é a tabela de capabilities, não a saúde. Se
    este teste começar a exigir False, a confiabilidade semântica vazou para
    dentro do modelo de saúde.
    """
    saude = SaudeDoWindowTitle.de("Netflix - Home - Netflix")

    assert saude.parseable is True


def test_a_confiabilidade_semantica_continua_nas_capabilities():
    """A saúde não sabe qual serviço nomeia a obra; a capability sabe."""
    from app.media.now_playing import PLATAFORMAS_COM_OBRA_NA_JANELA

    assert "DISNEY_PLUS" in PLATAFORMAS_COM_OBRA_NA_JANELA
    # O Max continua fora, e é ele que sustenta o princípio: a janela dele
    # SEMPRE tem título e ele SEMPRE é o do episódio. Não é falta de frescor,
    # é falta de capacidade — esperar mais não melhora.
    assert "MAX" not in PLATAFORMAS_COM_OBRA_NA_JANELA
    # E nada disso aparece no modelo de saúde.
    assert "platform" not in SaudeDoWindowTitle.__dataclass_fields__


# ── SMTC: disponibilidade no tempo ────────────────────────────────────────


def test_available_e_responsive_respondem_coisas_diferentes():
    """Confundir as duas foi o que fez o Disney+ sumir: a SMTC ESTAVA
    disponível — o Windows tem a API, o módulo importa — e não estava
    respondendo."""
    campos = set(SaudeDaSMTC.__dataclass_fields__)

    assert campos == {"available", "responsive", "lastSuccess", "latency", "timeout"}


@pytest.mark.asyncio
async def test_uma_leitura_bem_sucedida_registra_sucesso_e_latencia():
    class _Rapido:
        async def read(self):
            return None

    leitura = LeituraEmVoo(_Rapido())
    await leitura.ler()          # dispara
    await asyncio.sleep(0)       # deixa a tarefa completar
    await leitura.ler()          # colhe

    saude = SaudeDaSMTC.de(leitura)

    assert saude.responsive is True
    assert saude.lastSuccess is not None
    assert saude.latency is not None
    assert saude.latency >= 0.0


@pytest.mark.asyncio
async def test_uma_leitura_pendurada_deixa_de_ser_responsiva(monkeypatch):
    class _Pendurado:
        async def read(self):
            await asyncio.Event().wait()

    monkeypatch.setattr(LeituraEmVoo, "SEGUNDOS_ATE_DESISTIR", 0.0)
    leitura = LeituraEmVoo(_Pendurado())
    await leitura.ler()
    await leitura.ler()

    saude = SaudeDaSMTC.de(leitura)

    assert saude.responsive is False
    # Nunca voltou, então não há sucesso nem latência para relatar — e `None`
    # aqui é "não sei", não "zero".
    assert saude.lastSuccess is None
    assert saude.latency is None
    assert saude.timeout == 0.0


@pytest.mark.asyncio
async def test_a_instrumentacao_nao_mexe_no_fluxo_de_controle():
    """O gate da Fase 3 é "mesmos inputs, mesmos outputs".

    A leitura continua devolvendo o mesmo objeto de antes; a saúde é derivada
    por fora. Se alguém fizer a `LeituraEmVoo` decidir algo a partir de
    `ultima_latencia`, este teste não pega — mas os characterization tests da
    Fase 0 pegam, e é para isso que eles existem.
    """
    marcador = object()

    class _Fixo:
        async def read(self):
            return marcador

    leitura = LeituraEmVoo(_Fixo())
    await leitura.ler()
    await asyncio.sleep(0)

    assert await leitura.ler() is marcador
    assert leitura.ultima_latencia is not None
