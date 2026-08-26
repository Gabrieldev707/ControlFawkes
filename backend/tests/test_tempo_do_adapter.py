"""O tempo que vem da PÁGINA, quando o `<video>` é cego para o próprio conteúdo.

## O que se mediu

Disney+, Gavião Arqueiro T1:E1, sonda de DOM no console em 26/08/2026. Tudo no
MESMO instante:

    slider do player   aria-valuenow=146  aria-valuemax=3043  ("2:26 of 50:43")
    video.currentTime  50.8
    video.duration     Infinity
    video.seekable     [0, 62]

O `seekable` inteiro cabia em 62 segundos, num episódio de cinquenta minutos.
O elemento não está com defeito: ele reporta a janela DASH que está montando
naquele momento, e essa janela não é o episódio. `currentTime` não é a posição,
`duration` não é a duração, e a posição que o ControlFawkes mostrava para
Disney+ nunca esteve certa — não por regressão, mas porque a única fonte que
existia era a errada.

Antes disto o defeito aparecia como "contagem falsa": a barra sempre quase
cheia e o "faltam X" sempre em segundos. Foram DOIS diagnósticos errados até
aqui — "prévia de menos de 90s" e "borda de buffer" —, e os dois erravam pelo
mesmo motivo: tratavam o número como se ele descrevesse a obra e estivesse
apenas impreciso.

## A regra

O adapter só declara tempo quando SABE. Nos serviços cujo `<video>` já
responde — que é a regra, e a Netflix é o caso — ele não manda nada, e nada
muda. É isso que torna seguro pôr `provider-adapter` na frente em
`FIELD_AUTHORITY`.

E declarar velho não basta: tempo é campo dinâmico, e `dinamicos_frescos`
derruba o adapter parado antes de ele vencer. Nome de obra não — o nome de um
minuto atrás continua sendo o nome da obra.
"""

from __future__ import annotations

import pytest

from app.bridge.estado import (
    SEGUNDOS_ATE_O_TEMPO_ENVELHECER,
    EstadoDaPonte,
)
from app.bridge.eventos import EventoDeMidia, Recusa, validar
from app.bridge.merger import FIELD_AUTHORITY, fundir
from app.media.fusao import fundir_com_a_ponte


def mensagem(**payload: object) -> dict:
    base: dict = {
        "sessionId": "s1",
        "provider": "www.disneyplus.com",
        "playbackState": "playing",
        "currentTime": 50.8,
        "duration": None,
        "documentTitle": "Gavião Arqueiro | Disney+",
        "workTitle": "Gavião Arqueiro",
        "episodeTitle": "Nunca Conheça seus Heróis",
        "seasonNumber": 1,
        "episodeNumber": 1,
        "adapterPosition": 146.0,
        "adapterDuration": 3043.0,
    }
    base.update(payload)
    return {
        "protocolVersion": 1,
        "messageType": "POSITION_SYNC",
        "timestamp": 0.0,
        "payload": base,
    }


def validado(**payload: object) -> EventoDeMidia:
    resultado = validar(mensagem(**payload), agora=1000.0)
    assert isinstance(resultado, EventoDeMidia), resultado
    return resultado


def ponte(agora: float = 0.0, **payload: object) -> EstadoDaPonte:
    estado = EstadoDaPonte()
    estado.registrar(validado(**payload), agora=agora)
    return estado


# ── A validação ───────────────────────────────────────────────────────────

class TestValidacao:
    def test_o_par_do_adapter_atravessa(self):
        evento = validado()

        assert evento.adapterPosition == pytest.approx(146.0)
        assert evento.adapterDuration == pytest.approx(3043.0)
        # E NÃO substitui o do elemento: são duas fontes, e quem escolhe entre
        # elas é o Merger. Apagar uma aqui seria decidir autoridade dentro da
        # validação.
        assert evento.currentTime == pytest.approx(50.8)

    def test_sem_o_par_os_campos_ficam_ausentes(self):
        """O caso da Netflix, e de todo serviço sem adapter de tempo."""
        evento = validado(adapterPosition=None, adapterDuration=None)

        assert evento.adapterPosition is None
        assert evento.adapterDuration is None

    def test_posicao_alem_do_fim_derruba_o_PAR_e_nao_a_mensagem(self):
        """Um DOM ruim não pode calar o serviço inteiro.

        A mensagem segue valendo pelo elemento e pela metadata — que é o
        contrário do `currentTime` além do fim, onde a mensagem inteira é
        recusada porque ali não sobra nada confiável.
        """
        evento = validado(adapterPosition=4000.0, adapterDuration=3043.0)

        assert evento.adapterPosition is None
        assert evento.adapterDuration is None
        assert evento.workTitle == "Gavião Arqueiro"
        assert evento.currentTime == pytest.approx(50.8)

    @pytest.mark.parametrize(
        ("posicao", "duracao"),
        [(-1.0, 3043.0), ("muito", 3043.0), (float("nan"), 3043.0)],
    )
    def test_posicao_impossivel_vira_ausente(self, posicao, duracao):
        assert validado(adapterPosition=posicao, adapterDuration=duracao).adapterPosition is None

    @pytest.mark.parametrize("duracao", [0.0, -10.0, float("inf")])
    def test_duracao_impossivel_vira_ausente(self, duracao):
        """`Infinity` é exatamente o que o `<video>` do Disney+ publica."""
        assert validado(adapterDuration=duracao).adapterDuration is None


# ── A tabela de autoridade ────────────────────────────────────────────────

class TestAutoridade:
    def test_o_adapter_vem_antes_do_elemento_no_tempo(self):
        assert FIELD_AUTHORITY["currentTime"][0] == "provider-adapter"
        assert FIELD_AUTHORITY["duration"][0] == "provider-adapter"

    def test_a_janela_continua_sem_medir_tempo(self):
        """A janela nomeia obra e não mede nada. Regra que não muda."""
        assert "window-title" not in FIELD_AUTHORITY["currentTime"]
        assert "window-title" not in FIELD_AUTHORITY["duration"]

    def test_o_estado_tecnico_continua_com_o_elemento(self):
        """`paused` o `<video>` sabe de si — o adapter não melhora isso."""
        assert FIELD_AUTHORITY["playbackState"][0] == "html-media-element"


# ── O que o Merger faz com as duas leituras ───────────────────────────────

class TestNoMerger:
    def test_o_tempo_do_adapter_vence_o_do_elemento(self):
        estado = ponte()

        sessao = fundir(estado.leituras(agora=0.0))

        assert sessao.currentTime.value == pytest.approx(146.0)
        assert sessao.currentTime.source == "provider-adapter"
        assert sessao.duration.value == pytest.approx(3043.0)

    def test_sem_adapter_o_elemento_continua_mandando(self):
        """A Netflix, e todo serviço cujo `<video>` já sabe a posição."""
        estado = ponte(
            provider="www.netflix.com",
            adapterPosition=None,
            adapterDuration=None,
            duration=3000.0,
        )

        sessao = fundir(estado.leituras(agora=0.0))

        assert sessao.currentTime.value == pytest.approx(50.8)
        assert sessao.currentTime.source == "html-media-element"
        assert sessao.duration.value == pytest.approx(3000.0)

    def test_o_adapter_parado_perde_o_TEMPO_e_mantem_o_NOME(self):
        """A assimetria da Fase 8, agora dentro de uma fonte só.

        A aba parou de bater: a posição de dois minutos atrás está errada
        AGORA, e o nome da obra de dois minutos atrás continua sendo o nome da
        obra.
        """
        estado = ponte(agora=0.0)
        muito_depois = SEGUNDOS_ATE_O_TEMPO_ENVELHECER + 1.0

        sessao = fundir(estado.leituras(agora=muito_depois))

        assert sessao.currentTime.value is None
        assert sessao.workTitle.value == "Gavião Arqueiro"
        assert sessao.seasonNumber.value == 1


# ── O cartão, que é onde isso aparece para a pessoa ───────────────────────

class TestNoCartao:
    def test_a_posicao_do_cartao_e_a_do_player(self):
        """`_da_ponte` não passa pelo Merger, e precisa da mesma ordem.

        É o caminho vivo desta máquina: a SMTC está pendurada e nunca
        respondeu, então não há leitura do Windows para fundir.
        """
        lida = fundir_com_a_ponte(None, ponte(), agora=0.0)

        assert lida is not None
        assert lida.position_seconds == pytest.approx(146.0)
        assert lida.duration_seconds == pytest.approx(3043.0)
        assert lida.title == "Gavião Arqueiro"
        assert lida.episode == "T1 E1 · Nunca Conheça seus Heróis"

    def test_sem_tempo_do_adapter_o_cartao_usa_o_elemento(self):
        lida = fundir_com_a_ponte(
            None,
            ponte(
                provider="www.netflix.com",
                adapterPosition=None,
                adapterDuration=None,
                duration=3000.0,
            ),
            agora=0.0,
        )

        assert lida is not None
        assert lida.position_seconds == pytest.approx(50.8)
        assert lida.duration_seconds == pytest.approx(3000.0)

    def test_a_duracao_falsa_do_elemento_nao_reaparece(self):
        """O `Infinity` do Disney+ não pode voltar por baixo.

        `duration` chega nula justamente porque `Infinity` foi recusado na
        validação, e o cartão tem de mostrar a duração REAL, não a ausência.
        """
        lida = fundir_com_a_ponte(None, ponte(duration=float("inf")), agora=0.0)

        assert lida is not None
        assert lida.duration_seconds == pytest.approx(3043.0)


# ── A projeção entre batimentos ───────────────────────────────────────────

class TestProjecao:
    def test_projeta_enquanto_toca(self):
        """A extensão bate de dez em dez segundos; o cartão anda no meio."""
        estado = ponte(agora=0.0)

        sessao = estado.atual(agora=8.0)
        assert sessao is not None
        assert sessao.posicao_do_adapter_agora(8.0) == pytest.approx(154.0)

    def test_pausado_nao_projeta(self):
        """O tempo passa, o filme não."""
        estado = ponte(agora=0.0, playbackState="paused")

        sessao = estado.atual(agora=8.0)
        assert sessao is not None
        assert sessao.posicao_do_adapter_agora(8.0) == pytest.approx(146.0)

    def test_a_projecao_para_no_fim_do_episodio(self):
        """Passar do fim é batimento que não chegou, não pessoa que assistiu além."""
        # Dentro do prazo de desconexão: passar dele apagaria a sessão, e o
        # teste estaria medindo outra coisa.
        estado = ponte(agora=0.0, adapterPosition=3040.0)

        sessao = estado.atual(agora=200.0)
        assert sessao is not None
        assert sessao.posicao_do_adapter_agora(200.0) == pytest.approx(3043.0)

    def test_o_par_sobrevive_ao_overlay_sumir(self):
        """Medido: depois de 12s sem mouse, o overlay inteiro sai do DOM.

        Nesses batimentos o adapter projeta pela âncora e continua mandando o
        par. Mas se um evento chegar SEM ele — um `PAUSE`, por exemplo —, o
        último par conhecido não pode ser apagado: apagá-lo tiraria a barra da
        tela no meio do episódio.
        """
        estado = ponte(agora=0.0)
        estado.registrar(
            validado(
                messageType="PAUSE",
                adapterPosition=None,
                adapterDuration=None,
                currentTime=None,
            ),
            agora=1.0,
        )

        sessao = estado.atual(agora=1.0)
        assert sessao is not None
        assert sessao.adapterDuration == pytest.approx(3043.0)
        assert sessao.adapterPosition == pytest.approx(146.0)
