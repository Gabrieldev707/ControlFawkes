"""Fase 14 — Multiple Tabs: telemetria.

O gate:

    Dataset real coletado.
    Casos ambíguos identificados.
    Nenhuma política congelada antes dos dados.

A terceira frase é a que manda, e é uma proibição: o árbitro da Fase 15 não
pode ser escrito de cabeça. Estes testes provam que o coletor OBSERVA — e não
que ele decide, porque decidir aqui seria violar o gate.
"""

from __future__ import annotations

import json

import pytest

from app.bridge.estado import EstadoDaPonte
from app.bridge.eventos import validar
from app.bridge.estado import SessaoDaPonte
from app.bridge.telemetria import ColetorDeAbas, caso_de, resumir, uma_por_aba


def sessao(**overrides: object) -> SessaoDaPonte:
    """Uma sessão da ponte, montada direto.

    Construir pelo `EstadoDaPonte` não serve aqui: ele agora encerra a sessão
    anterior da mesma aba — que é justamente o caso que estes testes precisam
    montar para provar que o CLASSIFICADOR também se defende dele.
    """
    campos: dict = {
        "sessionId": "s1", "tabId": 1, "windowId": 1, "platform": "NETFLIX",
        "playbackState": "playing", "currentTime": 100.0, "duration": 3238.0,
        "playbackRate": 1.0, "muted": False, "audible": None,
        "workTitle": None, "episodeTitle": None, "seasonNumber": None,
        "episodeNumber": None, "pageId": None,
        "adapterPosition": None, "adapterDuration": None, "documentTitle": None,
        "active": None, "windowFocused": None, "tabMuted": None,
        "pictureInPicture": None, "visible": None,
        "msDesdeUltimoPlay": None, "msDesdeUltimoEvento": None,
        "visto_em": 0.0, "posicao_em": 0.0,
    }
    campos.update(overrides)
    return SessaoDaPonte(**campos)


def evento(estado: EstadoDaPonte, agora: float = 0.0, **payload: object) -> None:
    base: dict = {
        "sessionId": "aba-1",
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


# ── A telemetria chega inteira ────────────────────────────────────────────

def test_a_telemetria_da_aba_atravessa_a_validacao():
    evento_validado = validar(
        {
            "protocolVersion": 1,
            "messageType": "POSITION_SYNC",
            "timestamp": 0.0,
            "payload": {
                "sessionId": "aba-1",
                "provider": "www.netflix.com",
                "tabId": 7,
                "windowId": 3,
                "active": True,
                "windowFocused": False,
                "audible": True,
                "tabMuted": False,
                "pictureInPicture": True,
                "visible": False,
                "msDesdeUltimoPlay": 4200.0,
                "msDesdeUltimoEvento": 120.0,
            },
        },
        agora=1000.0,
    )

    assert evento_validado.tabId == 7
    assert evento_validado.active is True
    assert evento_validado.windowFocused is False
    assert evento_validado.audible is True
    assert evento_validado.pictureInPicture is True
    assert evento_validado.visible is False
    assert evento_validado.msDesdeUltimoPlay == 4200.0


def test_intervalo_negativo_e_relogio_torto_e_vira_ausente():
    evento_validado = validar(
        {
            "protocolVersion": 1,
            "messageType": "POSITION_SYNC",
            "timestamp": 0.0,
            "payload": {
                "sessionId": "aba-1",
                "msDesdeUltimoPlay": -500.0,
            },
        },
        agora=1000.0,
    )

    assert evento_validado.msDesdeUltimoPlay is None


def test_a_telemetria_nao_e_herdada_do_evento_anterior():
    """"a aba estava ativa há um minuto" não responde "a aba está ativa?".

    Herdar aqui produziria exatamente o dado plausível-e-errado que a Fase 8
    existe para recusar — e o dataset da Fase 14 ficaria descrevendo um estado
    que não existiu.
    """
    estado = EstadoDaPonte()
    evento(estado, active=True, audible=True)
    evento(estado, agora=1.0, active=None, audible=None)

    sessao = estado.atual(agora=1.0)
    assert sessao.active is None
    assert sessao.audible is None
    # E o que NÃO é telemetria continua herdando: a duração não sumiu.
    assert sessao.duration == 3238.0


# ── Casos ambíguos identificados ──────────────────────────────────────────

def duas_abas(primeira: dict | None = None, **segunda: object) -> list:
    estado = EstadoDaPonte()
    uma = dict(sessionId="aba-1")
    uma.update(primeira or {})
    evento(estado, **uma)
    outra = dict(sessionId="aba-2", provider="www.youtube.com")
    outra.update(segunda)
    evento(estado, agora=1.0, **outra)
    return estado.vivas(agora=1.0)


def test_uma_aba_sozinha_nao_e_caso_nenhum():
    estado = EstadoDaPonte()
    evento(estado)

    assert caso_de(estado.vivas(agora=0.0)) == "uma-aba"


@pytest.mark.parametrize(
    ("segunda", "esperado"),
    [
        # Netflix + YouTube, as duas tocando.
        ({"playbackState": "playing"}, "duas-tocando"),
        # A aba selecionada está pausada e outra toca atrás.
        ({"playbackState": "paused", "active": True}, "ativa-pausada-outra-tocando"),
        # PiP vence tudo: a aba pode estar atrás e a pessoa assistindo.
        ({"playbackState": "paused", "pictureInPicture": True}, "pip"),
    ],
)
def test_os_casos_do_plano_tem_nome(segunda, esperado):
    """O dataset não pode depender de alguém reconhecer o padrão a olho."""
    assert caso_de(duas_abas(**segunda)) == esperado


def test_a_aba_que_toca_em_segundo_plano_tem_nome():
    """O caso que quebra "aba ativa é quem assiste".

    A aba que toca declara `active: false`. Ninguém está olhando para ela, e
    ainda assim é ela que está reproduzindo.
    """
    sessoes = duas_abas(
        primeira={"active": False, "playbackState": "playing"},
        playbackState="paused",
    )

    assert caso_de(sessoes) == "background-tocando"


def test_servicos_diferentes_e_um_caso_proprio():
    estado = EstadoDaPonte()
    evento(estado, sessionId="aba-1", playbackState="paused")
    evento(estado, agora=1.0, sessionId="aba-2",
           provider="www.youtube.com", playbackState="paused")

    assert caso_de(estado.vivas(agora=1.0)) == "servicos-diferentes"


# ── O coletor ─────────────────────────────────────────────────────────────

def test_uma_aba_sozinha_nao_gera_linha(tmp_path):
    """Gravar uma linha por segundo para dizer "não há ambiguidade" encheria o
    disco com o caso que não interessa."""
    estado = EstadoDaPonte()
    evento(estado)
    coletor = ColetorDeAbas(caminho=tmp_path / "abas.jsonl")

    assert coletor.observar(estado.vivas(agora=0.0), agora=0.0) is False
    assert not (tmp_path / "abas.jsonl").exists()


def test_duas_abas_geram_linha(tmp_path):
    caminho = tmp_path / "abas.jsonl"
    coletor = ColetorDeAbas(caminho=caminho)

    assert coletor.observar(duas_abas(playbackState="playing"), agora=0.0) is True

    linha = json.loads(caminho.read_text(encoding="utf-8").strip())
    assert linha["caso"] == "duas-tocando"
    assert len(linha["abas"]) == 2


def test_o_coletor_nao_grava_a_cada_volta_do_laco(tmp_path):
    """O laço roda uma vez por segundo e a maioria das voltas é idêntica.

    Gravar todas daria milhares de linhas repetidas escondendo as poucas que
    mudaram.
    """
    coletor = ColetorDeAbas(caminho=tmp_path / "abas.jsonl")
    sessoes = duas_abas(playbackState="playing")

    gravadas = sum(
        1 for segundo in range(20)
        if coletor.observar(sessoes, agora=float(segundo))
    )

    assert gravadas == 4


def test_o_dataset_nao_guarda_navegacao(tmp_path):
    """Nome de obra, endereço e id de reprodução não entram.

    Um arquivo de diagnóstico com essas três coisas vira histórico de navegação
    por acidente.
    """
    caminho = tmp_path / "abas.jsonl"
    estado = EstadoDaPonte()
    evento(estado, sessionId="aba-1", workTitle="Sherlock", pageId="81234567")
    evento(estado, agora=1.0, sessionId="aba-2", provider="www.youtube.com",
           workTitle="Um vídeo qualquer", playbackState="playing")

    ColetorDeAbas(caminho=caminho).observar(estado.vivas(agora=1.0), agora=0.0)

    bruto = caminho.read_text(encoding="utf-8")
    assert "Sherlock" not in bruto
    assert "81234567" not in bruto
    assert "netflix.com" not in bruto
    # O serviço fica: "Netflix + YouTube" não é uma pergunta sem ele.
    assert "NETFLIX" in bruto and "YOUTUBE" in bruto


def test_o_teto_de_linhas_e_respeitado(tmp_path):
    caminho = tmp_path / "abas.jsonl"
    coletor = ColetorDeAbas(caminho=caminho, maximo=3)
    sessoes = duas_abas(playbackState="playing")

    for segundo in range(0, 100, 10):
        coletor.observar(sessoes, agora=float(segundo))

    assert len(caminho.read_text(encoding="utf-8").strip().splitlines()) == 3


def test_o_resumo_diz_se_ja_da_para_escrever_a_politica(tmp_path):
    """A pergunta que fecha a Fase 14: os cenários do plano já têm dados?"""
    caminho = tmp_path / "abas.jsonl"
    coletor = ColetorDeAbas(caminho=caminho)
    coletor.observar(duas_abas(playbackState="playing"), agora=0.0)
    coletor.observar(duas_abas(pictureInPicture=True, playbackState="paused"), agora=100.0)

    assert resumir(caminho) == {"duas-tocando": 1, "pip": 1}


def test_dataset_inexistente_nao_estoura(tmp_path):
    assert resumir(tmp_path / "nao-existe.jsonl") == {}


def test_o_teto_vale_para_o_arquivo_e_nao_para_a_execucao(tmp_path):
    """`_linhas` começava em zero a cada processo.

    O limite nunca alcançava um arquivo acumulado entre reinícios: cada restart
    devolvia outras 5000 linhas de crédito, e num servidor que sobe várias
    vezes por dia o teto era decorativo.
    """
    caminho = tmp_path / "abas.jsonl"
    sessoes = duas_abas(playbackState="playing")

    primeiro = ColetorDeAbas(caminho=caminho, maximo=3)
    for segundo in range(0, 100, 10):
        primeiro.observar(sessoes, agora=float(segundo))
    assert len(caminho.read_text(encoding="utf-8").strip().splitlines()) == 3

    # Um processo novo, o mesmo arquivo: o teto continua valendo.
    segundo_processo = ColetorDeAbas(caminho=caminho, maximo=3)
    for segundo in range(0, 100, 10):
        segundo_processo.observar(sessoes, agora=float(segundo))

    assert len(caminho.read_text(encoding="utf-8").strip().splitlines()) == 3



# ── Contar ABAS, e não sessões ────────────────────────────────────────────
#
# O classificador contava sessões e chamava isso de abas. Com sessões fantasma
# vivas na mesma aba — o defeito corrigido em `_esquecer_a_mesma_aba` —, cada
# fantasma virava uma aba a mais e o dataset inteiro ficou torto.
#
# Medido em 26/08/2026, relendo as 1526 observações com telemetria:
#
#     instantes com sessões repetidas na mesma aba   1078 de 1526
#     maior número de sessões numa única aba         8
#
# E na leitura:
#
#                                 contando sessões   contando ABAS
#     instantes com 2+ tocando           477               18
#
# Vinte e seis vezes. O árbitro da Fase 15 teria sido escrito para um conflito
# que quase não acontece.

class TestUmaSessaoPorAba:
    def test_duas_sessoes_da_mesma_aba_sao_UMA_aba(self):
        sessoes = [sessao(tabId=7, sessionId="fantasma"), sessao(tabId=7, sessionId="viva")]

        assert len(uma_por_aba(sessoes)) == 1
        # Uma aba só não é ambiguidade nenhuma.
        assert caso_de(sessoes) == "uma-aba"

    def test_a_mais_recente_vence(self):
        """Mesma ordem de `_esquecer_a_mesma_aba`: a última descreve o agora."""
        antiga = sessao(tabId=7, sessionId="antiga", playbackState="paused")
        nova = sessao(tabId=7, sessionId="nova", playbackState="playing")

        assert uma_por_aba([antiga, nova]) == [nova]

    def test_abas_diferentes_continuam_duas(self):
        sessoes = [sessao(tabId=1), sessao(tabId=2)]

        assert len(uma_por_aba(sessoes)) == 2

    def test_sem_tabId_nada_e_deduplicado(self):
        """Sem `tabId` não há aba a comparar, e apagar jogaria fora dado bom."""
        sessoes = [sessao(tabId=None, sessionId="a"), sessao(tabId=None, sessionId="b")]

        assert len(uma_por_aba(sessoes)) == 2

    def test_o_fantasma_nao_inventa_duas_tocando(self):
        """O artefato exato que contaminou o dataset."""
        sessoes = [
            sessao(tabId=7, sessionId="fantasma", playbackState="playing"),
            sessao(tabId=7, sessionId="viva", playbackState="playing"),
        ]

        assert caso_de(sessoes) != "duas-tocando"

    def test_duas_abas_de_verdade_tocando_continuam_sendo_duas(self):
        sessoes = [
            sessao(tabId=1, playbackState="playing"),
            sessao(tabId=2, playbackState="playing"),
        ]

        assert caso_de(sessoes) == "duas-tocando"
