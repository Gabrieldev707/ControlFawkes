"""Fase 16 — o comando descendo até o `<video>`.

Até aqui a ponte só falava para cima. O play/pause era uma TECLA: focar a
janela do Chrome e apertar a barra de espaço. Isso funciona, e continua sendo o
plano B — mas tem três limites, e dois deles estão medidos:

    rouba o foco    focar a janela tira o foco de onde a pessoa estava.

    erra de aba     a barra de espaço vai para a aba ATIVA. Medido na Fase 14:
                    em 6 dos 18 instantes com duas abas tocando havia MAIS DE
                    UMA aba ativa — janelas diferentes, cada uma com a sua.

    toggle cego     `MEDIA_PLAY_PAUSE` alterna o que estiver lá. Foi a queixa
                    "pausa e não volta a play".

E o caminho de descida é invertido de propósito: o host PERGUNTA se há comando,
em vez de ser chamado. Native Messaging é o Chrome quem inicia, e essa é a
propriedade que fez a Fase 1 preferi-lo a um WebSocket em localhost — que
qualquer página aberta alcança. Manter a propriedade custa inverter a pergunta.
"""

from __future__ import annotations

import asyncio

import pytest

from app.bridge.comandos import ACOES, FilaDeComandos


@pytest.fixture
def fila() -> FilaDeComandos:
    return FilaDeComandos()


# ── A fila ────────────────────────────────────────────────────────────────

class TestFila:
    @pytest.mark.asyncio
    async def test_um_comando_enfileirado_e_entregue(self, fila: FilaDeComandos):
        comando = fila.enfileirar("PAUSE", tabId=7, sessionId="s1")

        assert comando is not None
        entregue = await fila.proximo(espera=0.5)
        assert entregue is comando
        assert entregue.como_mensagem()["payload"]["acao"] == "PAUSE"

    @pytest.mark.asyncio
    async def test_sem_comando_a_espera_devolve_None(self, fila: FilaDeComandos):
        """Silêncio é a resposta normal: quase todo minuto não tem comando."""
        assert await fila.proximo(espera=0.05) is None

    @pytest.mark.asyncio
    async def test_a_espera_ACORDA_quando_o_comando_chega(self, fila: FilaDeComandos):
        """É isto que faz o botão responder na hora.

        Uma consulta a cada segundo daria até um segundo de atraso num botão
        que a pessoa acabou de apertar.
        """
        async def apertar():
            await asyncio.sleep(0.05)
            fila.enfileirar("PLAY", tabId=7, sessionId="s1")

        asyncio.create_task(apertar())
        comando = await fila.proximo(espera=2.0)

        assert comando is not None
        assert comando.acao == "PLAY"

    @pytest.mark.parametrize("acao", sorted(ACOES))
    def test_as_acoes_conhecidas_entram(self, fila: FilaDeComandos, acao: str):
        assert fila.enfileirar(acao, tabId=1, sessionId="s", valor=10.0) is not None

    @pytest.mark.parametrize("acao", ["FULLSCREEN", "VOLUME_UP", "", "play"])
    def test_uma_acao_desconhecida_nao_entra(self, fila: FilaDeComandos, acao: str):
        """Lista curta e fechada, como `eventos.TIPOS`: uma ação sem executor
        do outro lado é uma promessa que falha em silêncio."""
        assert fila.enfileirar(acao, tabId=1, sessionId="s") is None

    def test_a_fila_cheia_recusa_em_vez_de_acumular(self, fila: FilaDeComandos):
        """Ninguém consumindo é Chrome fechado. Guardar tudo para entregar de
        uma vez faria a pessoa apertar play e receber dez comandos velhos."""
        aceitos = [
            fila.enfileirar("PAUSE", tabId=1, sessionId="s") for _ in range(200)
        ]

        assert None in aceitos
        assert fila.pendentes <= 32


# ── O resultado voltando ──────────────────────────────────────────────────

class TestResultado:
    @pytest.mark.asyncio
    async def test_a_pagina_responde_e_quem_pediu_recebe(self, fila: FilaDeComandos):
        comando = fila.enfileirar("PAUSE", tabId=7, sessionId="s1")

        async def responder():
            await asyncio.sleep(0.02)
            fila.resolver(comando.id, ok=True)

        asyncio.create_task(responder())
        resultado = await fila.esperar(comando, ate=1.0)

        assert resultado is not None
        assert resultado.ok is True

    @pytest.mark.asyncio
    async def test_sem_resposta_a_tempo_devolve_None(self, fila: FilaDeComandos):
        """`None` é o sinal para o plano B — a tecla.

        Quem apertou o botão está olhando para a tela: melhor tentar de outro
        jeito do que esperar uma resposta que talvez nunca venha.
        """
        comando = fila.enfileirar("PAUSE", tabId=7, sessionId="s1")

        assert await fila.esperar(comando, ate=0.05) is None

    @pytest.mark.asyncio
    async def test_uma_resposta_ATRASADA_nao_e_erro(self, fila: FilaDeComandos):
        """Chegar depois de quem pediu desistir não pode explodir nada."""
        comando = fila.enfileirar("PAUSE", tabId=7, sessionId="s1")
        await fila.esperar(comando, ate=0.05)

        # Ninguém mais espera: `resolver` diz isso em vez de fingir sucesso.
        assert fila.resolver(comando.id, ok=True) is False

    def test_um_id_desconhecido_nao_explode(self, fila: FilaDeComandos):
        assert fila.resolver("nao-existe", ok=True) is False

    @pytest.mark.asyncio
    async def test_a_falha_da_pagina_chega_como_falha(self, fila: FilaDeComandos):
        comando = fila.enfileirar("SEEK_TO", tabId=7, sessionId="s1", valor=99.0)
        fila.resolver(comando.id, ok=False, detalhe="sem elemento")

        resultado = await fila.esperar(comando, ate=1.0)

        assert resultado.ok is False
        assert resultado.detalhe == "sem elemento"


# ── O endereço: o gate pede que a aba errada não receba ───────────────────

class TestEndereco:
    def test_o_comando_carrega_aba_E_reproducao(self):
        """Duas travas, e cada uma pega um caso diferente.

        `tabId` impede acertar a aba errada quando há várias tocando.
        `sessionId` impede acertar a reprodução errada na aba certa: se ela
        trocou de episódio entre o pedido e a chegada, pausar o seguinte porque
        o anterior foi pedido é pior do que não pausar nada.
        """
        fila = FilaDeComandos()
        comando = fila.enfileirar("PAUSE", tabId=42, sessionId="ep-3")

        payload = comando.como_mensagem()["payload"]
        assert payload["tabId"] == 42
        assert payload["sessionId"] == "ep-3"

    def test_cada_comando_tem_id_proprio(self):
        fila = FilaDeComandos()
        ids = {fila.enfileirar("PLAY", tabId=1, sessionId="s").id for _ in range(20)}

        assert len(ids) == 20


# ── A resposta que chega adiantada ────────────────────────────────────────

class TestRespostaAdiantada:
    @pytest.mark.asyncio
    async def test_a_resposta_que_chega_antes_de_alguem_esperar_nao_se_perde(self):
        """No dispatcher isso não acontece — entre `enfileirar` e `esperar` não
        há `await`. Mas depender dessa coincidência é o tipo de coisa que
        funciona até o dia em que alguém põe um `await` ali."""
        fila = FilaDeComandos()
        comando = fila.enfileirar("PAUSE", tabId=7, sessionId="s1")

        fila.resolver(comando.id, ok=True, detalhe="já era")
        resultado = await fila.esperar(comando, ate=0.05)

        assert resultado is not None
        assert resultado.ok is True
        assert resultado.detalhe == "já era"

    @pytest.mark.asyncio
    async def test_a_resposta_adiantada_e_consumida_uma_vez_so(self):
        fila = FilaDeComandos()
        comando = fila.enfileirar("PAUSE", tabId=7, sessionId="s1")
        fila.resolver(comando.id, ok=True)

        assert (await fila.esperar(comando, ate=0.05)) is not None
        assert (await fila.esperar(comando, ate=0.05)) is None

    def test_as_adiantadas_nao_crescem_para_sempre(self):
        """Um processo que fica ligado por dias não pode acumular lixo."""
        fila = FilaDeComandos()
        for i in range(500):
            fila.resolver(f"orfao-{i}", ok=True)

        assert len(fila._resultados) <= 32


# ── O gate da Fase 16, no dispatcher ──────────────────────────────────────

from app.bridge.estado import EstadoDaPonte, SessaoDaPonte  # noqa: E402
from app.protocol import dispatcher as modulo_do_dispatcher  # noqa: E402
from app.protocol.dispatcher import Dispatcher  # noqa: E402
from app.windows.focus import WindowFocuser  # noqa: E402


def sessao_da_ponte(**overrides: object) -> SessaoDaPonte:
    """Uma sessão VIVA.

    `visto_em` no relógio monotônico de agora, e não zero: `atual_de` descarta
    sessões que não falam há cinco minutos, e uma sessão nascida em zero já
    nasce morta — o teste passaria a medir o prazo de desconexão em vez do
    comando.
    """
    import time as _t

    campos: dict = {
        "sessionId": "s1", "tabId": 7, "windowId": 1, "platform": "NETFLIX",
        "playbackState": "playing", "currentTime": 100.0, "duration": 3238.0,
        "playbackRate": 1.0, "muted": False, "audible": None,
        "workTitle": "Uma Obra", "episodeTitle": None, "seasonNumber": None,
        "episodeNumber": None, "pageId": "111",
        "adapterPosition": None, "adapterDuration": None, "documentTitle": None,
        "active": None, "windowFocused": None, "tabMuted": None,
        "pictureInPicture": None, "visible": None,
        "msDesdeUltimoPlay": None, "msDesdeUltimoEvento": None,
        "visto_em": _t.monotonic(), "posicao_em": _t.monotonic(),
    }
    campos.update(overrides)
    return SessaoDaPonte(**campos)


@pytest.fixture
def montado(monkeypatch):
    """Um dispatcher com a ponte viva e uma fila limpa."""
    fila = FilaDeComandos()
    monkeypatch.setattr(modulo_do_dispatcher, "fila_de_comandos", fila)
    estado = EstadoDaPonte()
    d = Dispatcher(
        catalog=None,
        window_focuser=WindowFocuser(window_lister=lambda: []),
        bridge_state=estado,
    )
    return d, estado, fila


class TestOComandoChegaNaSessaoCerta:
    @pytest.mark.asyncio
    async def test_tocando_vira_PAUSE_e_pausado_vira_PLAY(self, montado):
        """Não é um toggle cego.

        `MEDIA_PLAY_PAUSE` alterna o que estiver lá, e quando o estado real e o
        suposto divergem o botão faz o contrário do desenhado — foi a queixa
        "pausa e não volta a play". Aqui o estado vem da própria página.
        """
        d, estado, fila = montado

        estado._sessoes["s1"] = sessao_da_ponte(playbackState="playing")
        asyncio.create_task(d._comandar_pela_ponte("MEDIA_PLAY_PAUSE", "NETFLIX"))
        assert (await fila.proximo(espera=0.5)).acao == "PAUSE"

        estado._sessoes["s1"] = sessao_da_ponte(playbackState="paused")
        asyncio.create_task(d._comandar_pela_ponte("MEDIA_PLAY_PAUSE", "NETFLIX"))
        assert (await fila.proximo(espera=0.5)).acao == "PLAY"

    @pytest.mark.asyncio
    async def test_o_comando_carrega_a_aba_daquela_sessao(self, montado):
        d, estado, fila = montado
        estado._sessoes["s1"] = sessao_da_ponte(tabId=99, sessionId="s1")

        asyncio.create_task(d._comandar_pela_ponte("MEDIA_PLAY_PAUSE", "NETFLIX"))
        comando = await fila.proximo(espera=0.5)

        assert comando.tabId == 99
        assert comando.sessionId == "s1"

    @pytest.mark.asyncio
    async def test_os_saltos_viram_SEEK_BY(self, montado):
        d, estado, fila = montado
        estado._sessoes["s1"] = sessao_da_ponte()

        asyncio.create_task(d._comandar_pela_ponte("MEDIA_SEEK_BACK", "NETFLIX"))
        atras = await fila.proximo(espera=0.5)
        asyncio.create_task(d._comandar_pela_ponte("MEDIA_SEEK_FORWARD", "NETFLIX"))
        frente = await fila.proximo(espera=0.5)

        assert (atras.acao, atras.valor) == ("SEEK_BY", -10.0)
        assert (frente.acao, frente.valor) == ("SEEK_BY", 10.0)


class TestAAbaErradaNaoRecebe:
    @pytest.mark.asyncio
    async def test_o_comando_vai_para_a_aba_DAQUELE_servico(self, montado):
        """Duas abas, dois serviços. A tecla não sabe escolher; o comando sabe.

        Medido na Fase 14: em 6 dos 18 instantes com duas abas tocando havia
        MAIS DE UMA aba ativa — janelas diferentes, cada uma com a sua. A barra
        de espaço iria para qualquer uma delas.
        """
        d, estado, fila = montado
        estado._sessoes["netflix"] = sessao_da_ponte(
            sessionId="netflix", tabId=1, platform="NETFLIX",
        )
        estado._sessoes["disney"] = sessao_da_ponte(
            sessionId="disney", tabId=2, platform="DISNEY_PLUS",
        )

        asyncio.create_task(d._comandar_pela_ponte("MEDIA_PLAY_PAUSE", "NETFLIX"))
        comando = await fila.proximo(espera=0.5)

        assert comando.tabId == 1

    @pytest.mark.asyncio
    async def test_sem_sessao_daquele_servico_nao_enfileira_nada(self, montado):
        d, estado, fila = montado
        estado._sessoes["s1"] = sessao_da_ponte(platform="NETFLIX")

        assert await d._comandar_pela_ponte("MEDIA_PLAY_PAUSE", "MAX") is None
        assert fila.pendentes == 0

    @pytest.mark.asyncio
    async def test_sem_tabId_nao_enfileira(self, montado):
        """Sem endereço, o comando iria para qualquer lugar."""
        d, estado, fila = montado
        estado._sessoes["s1"] = sessao_da_ponte(tabId=None)

        assert await d._comandar_pela_ponte("MEDIA_PLAY_PAUSE", "NETFLIX") is None
        assert fila.pendentes == 0


class TestOEstadoRetornaCorretamente:
    @pytest.mark.asyncio
    async def test_a_pagina_confirmando_vira_sucesso(self, montado):
        d, estado, fila = montado
        estado._sessoes["s1"] = sessao_da_ponte()

        tarefa = asyncio.create_task(d._comandar_pela_ponte("MEDIA_PLAY_PAUSE", "NETFLIX"))
        comando = await fila.proximo(espera=0.5)
        fila.resolver(comando.id, ok=True)

        assert await tarefa is True

    @pytest.mark.asyncio
    async def test_a_pagina_recusando_cai_para_o_plano_B(self, montado):
        """"Sem elemento" ou "outra reprodução" são motivos para tentar de
        outro jeito, não para desistir."""
        d, estado, fila = montado
        estado._sessoes["s1"] = sessao_da_ponte()

        tarefa = asyncio.create_task(d._comandar_pela_ponte("MEDIA_PLAY_PAUSE", "NETFLIX"))
        comando = await fila.proximo(espera=0.5)
        fila.resolver(comando.id, ok=False, detalhe="sem elemento")

        assert await tarefa is None

    @pytest.mark.asyncio
    async def test_sem_resposta_a_tempo_cai_para_o_plano_B(self, montado, monkeypatch):
        """Quem não instalou a extensão continua com o controle que sempre teve."""
        d, estado, fila = montado
        estado._sessoes["s1"] = sessao_da_ponte()
        monkeypatch.setattr(modulo_do_dispatcher, "fila_de_comandos", fila)
        import app.bridge.comandos as modulo_comandos

        monkeypatch.setattr(modulo_comandos, "SEGUNDOS_ATE_DESISTIR", 0.05)

        assert await d._comandar_pela_ponte("MEDIA_PLAY_PAUSE", "NETFLIX") is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tipo", ["MEDIA_VOLUME_UP", "MEDIA_NEXT", "MEDIA_FULLSCREEN"])
    async def test_acoes_que_nao_sao_do_elemento_nao_descem(self, montado, tipo):
        """Uma ação sem executor do outro lado é uma promessa que falha em
        silêncio. Volume e tela cheia continuam pelo caminho de sempre."""
        d, estado, fila = montado
        estado._sessoes["s1"] = sessao_da_ponte()

        assert await d._comandar_pela_ponte(tipo, "NETFLIX") is None
        assert fila.pendentes == 0
