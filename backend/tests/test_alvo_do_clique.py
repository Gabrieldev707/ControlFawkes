"""Onde o clique de tela cheia mira.

A tela cheia é um duplo clique, e não uma tecla: o atalho de teclado é de cada
site e nenhum aplica igual — no Max, com a janela em foco, o F não fazia
absolutamente nada. Medido em 18/08/2026.

Mas o clique mirava o CENTRO DA JANELA, e isso só acerta o vídeo enquanto ele
ocupa o meio da tela. Dois casos medidos em que é falso:

    Prime Video    o vídeo toca em `/detail/`, com a lista de episódios e a
                   sinopse em volta. O centro da janela cai no conteúdo.
    Netflix        pausada no plano com anúncios, o meio da janela é do
                   anúncio — e o clique ainda mirava um link de anunciante,
                   que é pior do que não fazer nada.

Quem sabe onde o vídeo está é a página, e a extensão está dentro dela.
"""

from __future__ import annotations

import time

import pytest

from app.bridge.estado import EstadoDaPonte
from app.bridge.eventos import EventoDeMidia, validar
from app.protocol.dispatcher import Dispatcher
from app.windows.focus import WindowFocuser


def evento(**payload: object) -> EventoDeMidia:
    base: dict = {
        "sessionId": "aba-1", "provider": "www.primevideo.com",
        "playbackState": "playing", "currentTime": 100.0, "duration": 1329.0,
        "tabId": 7, "workTitle": "Batman: The Animated Series",
    }
    base.update(payload)
    resultado = validar(
        {"protocolVersion": 1, "messageType": "POSITION_SYNC",
         "timestamp": 0.0, "payload": base},
        agora=1000.0,
    )
    assert isinstance(resultado, EventoDeMidia), resultado
    return resultado


@pytest.fixture
def montado():
    estado = EstadoDaPonte()
    d = Dispatcher(
        catalog=None,
        window_focuser=WindowFocuser(window_lister=lambda: []),
        bridge_state=estado,
    )
    return d, estado


class TestOCentroDoVideo:
    def test_a_ponte_dizendo_onde_o_video_esta(self, montado):
        d, estado = montado
        estado.registrar(
            evento(videoCentroX=0.31, videoCentroY=0.62), agora=time.monotonic(),
        )

        assert d._centro_do_video("PRIME_VIDEO") == (0.31, 0.62)

    def test_sem_extensao_nao_ha_alvo(self, montado):
        """E aí o centro da janela continua sendo o melhor palpite disponível."""
        d, _estado = montado

        assert d._centro_do_video("PRIME_VIDEO") is None

    def test_a_sessao_sem_o_retangulo_nao_inventa_alvo(self, montado):
        d, estado = montado
        estado.registrar(evento(), agora=time.monotonic())

        assert d._centro_do_video("PRIME_VIDEO") is None

    def test_o_alvo_e_do_SERVICO_certo(self, montado):
        """Duas abas, dois serviços. Clicar no vídeo do outro é pior do que
        clicar no centro da janela — pelo menos o centro está na janela certa."""
        d, estado = montado
        agora = time.monotonic()
        estado.registrar(
            evento(sessionId="prime", tabId=1, videoCentroX=0.3, videoCentroY=0.3),
            agora=agora,
        )
        estado.registrar(
            evento(
                sessionId="netflix", tabId=2, provider="www.netflix.com",
                duration=3238.0, videoCentroX=0.9, videoCentroY=0.9,
            ),
            agora=agora,
        )

        assert d._centro_do_video("PRIME_VIDEO") == (0.3, 0.3)
        assert d._centro_do_video("NETFLIX") == (0.9, 0.9)


class TestAValidacaoDaFracao:
    @pytest.mark.parametrize("valor", [0.0, 0.5, 1.0])
    def test_dentro_da_janela_passa(self, valor):
        assert evento(videoCentroX=valor).videoCentroX == pytest.approx(valor)

    @pytest.mark.parametrize("valor", [-0.1, 1.5, 42.0, "meio", None, float("nan")])
    def test_fora_da_faixa_vira_ausente(self, valor):
        """Fora de 0 a 1 não é "quase certo": é outra janela, ou um vídeo
        rolado para fora da tela. Clicar ali erraria o alvo com a mesma
        confiança de acertar."""
        assert evento(videoCentroX=valor).videoCentroX is None

    def test_o_retangulo_HERDA_entre_batimentos(self):
        """Ele não muda entre um batimento e outro, e um evento que não o traga
        — um `PAUSE`, por exemplo — não pode apagar o alvo do clique."""
        estado = EstadoDaPonte()
        agora = time.monotonic()
        estado.registrar(evento(videoCentroX=0.4, videoCentroY=0.5), agora=agora)
        estado.registrar(evento(seq=9), agora=agora)

        viva = estado.atual(agora)
        assert (viva.videoCentroX, viva.videoCentroY) == (0.4, 0.5)


# ── O botão de tela cheia ─────────────────────────────────────────────────
#
# O duplo clique funciona em quem IMPLEMENTA duplo clique — Netflix e Disney+,
# onde ele foi testado quando nasceu. Prime e Max não implementam, e o relato do
# usuário em 26/08/2026 descreve exatamente dois cliques simples chegando:
#
#     "apertei 1 vez nada, 2 vezes nada, na 3ª um clique rápido no pausa e
#      despausa na mesma hora"
#
# Medido no Max, com a sonda:
#
#     button  data-testid="player-ux-fullscreen-button"
#             aria-label="Tela cheia"   title="Tela cheia (F)"

class TestBotaoDeTelaCheia:
    @pytest.mark.asyncio
    async def test_sem_a_posicao_do_botao_ele_nao_tenta(self, montado):
        """E aí o duplo clique no vídeo continua sendo o caminho."""
        d, estado = montado
        estado.registrar(evento(), agora=time.monotonic())

        assert await d._clicar_no_botao_de_tela_cheia("PRIME_VIDEO") is False

    @pytest.mark.asyncio
    async def test_sem_janela_nao_ha_onde_clicar(self, montado):
        d, estado = montado
        estado.registrar(
            evento(telaCheiaX=0.9, telaCheiaY=0.95), agora=time.monotonic(),
        )

        # O `window_focuser` deste dispatcher não lista janela nenhuma.
        assert await d._clicar_no_botao_de_tela_cheia("PRIME_VIDEO") is False

    def test_a_posicao_do_botao_atravessa_a_ponte(self):
        e = evento(telaCheiaX=0.9012, telaCheiaY=0.9511)

        assert e.telaCheiaX == pytest.approx(0.9012)
        assert e.telaCheiaY == pytest.approx(0.9511)

    @pytest.mark.parametrize("valor", [-0.01, 1.01, "canto", None])
    def test_uma_posicao_impossivel_vira_ausente(self, valor):
        assert evento(telaCheiaX=valor).telaCheiaX is None

    def test_a_posicao_do_botao_HERDA_entre_batimentos(self):
        """O botão some junto com os controles depois de alguns segundos sem
        mouse. Herdar é o que permite clicar nele quando ele não está visível
        AGORA — e ele volta para o mesmo lugar, porque o player não o move."""
        estado = EstadoDaPonte()
        agora = time.monotonic()
        estado.registrar(evento(telaCheiaX=0.9, telaCheiaY=0.95), agora=agora)
        # Batimento com os controles escondidos: o botão não está no DOM.
        estado.registrar(evento(seq=9), agora=agora)

        viva = estado.atual(agora)
        assert (viva.telaCheiaX, viva.telaCheiaY) == (0.9, 0.95)
