"""O Merger — e as divergências reais entre fontes que ele tem de resolver.

Cada caso aqui é uma discordância que ACONTECE, não uma hipótese: a SMTC dizendo
`playing` enquanto o vídeo está parado, a janela do Max nomeando o episódio, a
Netflix não nomeando nada. O que se testa é que a resposta é determinística e
que ninguém ganha a sessão inteira.
"""

from __future__ import annotations

import pytest

from app.bridge.contratos import MediaField, SessaoCanonica
from app.bridge.merger import CAMPOS_DINAMICOS, FIELD_AUTHORITY, Leitura, fundir


def campo(valor, confiavel: bool = True, fonte="smtc") -> MediaField:
    return MediaField(value=valor, source=fonte, trustworthy=confiavel)


def smtc(**campos) -> Leitura:
    return Leitura("smtc", {k: campo(v, fonte="smtc") for k, v in campos.items()})


def video(**campos) -> Leitura:
    return Leitura(
        "html-media-element",
        {k: campo(v, fonte="html-media-element") for k, v in campos.items()},
    )


# ── A tabela é completa e coerente ────────────────────────────────────────


def test_todo_campo_da_sessao_tem_autoridade_declarada():
    """Um campo fora da tabela nunca seria preenchido, e o defeito apareceria
    como "sumiu", que é o mais difícil de rastrear."""
    assert set(FIELD_AUTHORITY) == set(SessaoCanonica.__annotations__)


def test_a_janela_nao_e_autoridade_para_nenhum_campo_de_tempo():
    """O título da janela não mede nada. Deixá-lo na tabela de `currentTime`
    seria abrir a porta para o valor de uma fonte que não tem relógio."""
    for nome in CAMPOS_DINAMICOS:
        assert "window-title" not in FIELD_AUTHORITY[nome]


def test_o_video_nao_e_autoridade_para_o_nome_da_obra():
    """O `<video>` sabe que segundo está tocando e não sabe o que está tocando."""
    assert "html-media-element" not in FIELD_AUTHORITY["workTitle"]


# ── Divergência de estado ─────────────────────────────────────────────────


def test_smtc_playing_e_video_parado_resolve_pelo_video():
    """A discordância clássica. A SMTC do Windows guarda o último estado que o
    aplicativo publicou; o elemento da página é o que está de fato acontecendo."""
    sessao = fundir([smtc(playbackState="playing"), video(playbackState="paused")])

    assert sessao.playbackState.value == "paused"
    assert sessao.playbackState.source == "html-media-element"


def test_smtc_paused_e_video_tocando_tambem_resolve_pelo_video():
    """O par do caso acima — e ele importa: uma regra que só acertasse num
    sentido seria a fonte vencendo por acaso, não por autoridade."""
    sessao = fundir([smtc(playbackState="paused"), video(playbackState="playing")])

    assert sessao.playbackState.value == "playing"


def test_sem_o_video_a_smtc_responde_pelo_estado():
    """Autoridade é uma ORDEM, não um monopólio. Spotify Desktop não tem
    `<video>` nenhum, e a SMTC continua sendo quem responde."""
    sessao = fundir([smtc(playbackState="playing", currentTime=42.0)])

    assert sessao.playbackState.value == "playing"
    assert sessao.playbackState.source == "smtc"
    assert sessao.currentTime.value == 42.0


# ── Divergência de título ─────────────────────────────────────────────────


def test_a_janela_correta_vence_a_smtc_generica():
    """Medido em produção: a SMTC devolve "Google Chrome" como título e a janela
    devolve o nome da obra. Genérico não é título — e quem sabe disso é quem
    preenche o campo, marcando `trustworthy=False`."""
    sessao = fundir([
        Leitura("smtc", {"workTitle": campo("Google Chrome", confiavel=False)}),
        Leitura("window-title", {"workTitle": campo("O Justiceiro", fonte="window-title")}),
    ])

    assert sessao.workTitle.value == "O Justiceiro"
    assert sessao.workTitle.source == "window-title"


def test_o_adapter_vence_a_janela_mesmo_com_a_janela_correta():
    """O adapter não vence por estar certo — vence por ser autoridade. Se a
    ordem dependesse de quem parece melhor, ela deixaria de ser ordem."""
    sessao = fundir([
        Leitura("window-title", {"workTitle": campo("O Rei", fonte="window-title")}),
        Leitura("provider-adapter", {"workTitle": campo("O Rei", fonte="provider-adapter")}),
    ])

    assert sessao.workTitle.source == "provider-adapter"


def test_o_adapter_correto_vence_a_janela_generica():
    """Netflix: a janela diz "Netflix" e nunca nomeia a obra."""
    sessao = fundir([
        Leitura("window-title", {"workTitle": campo("Netflix", confiavel=False)}),
        Leitura("provider-adapter", {
            "workTitle": campo("Round 6", fonte="provider-adapter"),
        }),
    ])

    assert sessao.workTitle.value == "Round 6"


def test_a_janela_do_max_nomeia_o_episodio_e_nao_a_obra():
    """Capacidade, e não frescor: esperar mais não melhora o título do Max.
    O valor está certo — a afirmação "isto é a obra" é que seria falsa."""
    sessao = fundir([
        Leitura("window-title", {
            "workTitle": campo("Capítulo 3: O Vazio", confiavel=False),
            "episodeTitle": campo("Capítulo 3: O Vazio", fonte="window-title"),
        }),
    ])

    assert sessao.workTitle.value is None
    assert sessao.episodeTitle.value == "Capítulo 3: O Vazio"


def test_a_smtc_com_titulo_antigo_perde_para_o_adapter_atual():
    sessao = fundir([
        smtc(workTitle="Episódio anterior"),
        Leitura("provider-adapter", {
            "workTitle": campo("Episódio atual", fonte="provider-adapter"),
        }),
    ])

    assert sessao.workTitle.value == "Episódio atual"


# ── Frescor ───────────────────────────────────────────────────────────────


def test_fonte_prioritaria_velha_cede_o_tempo_para_a_secundaria_saudavel():
    """A aba parou de mandar posição. O `<video>` continua sendo autoridade
    para `currentTime` — mas o último valor dele não vale mais, e o campo passa
    para a próxima da fila em vez de congelar."""
    parado = Leitura(
        "html-media-element",
        {"currentTime": campo(10.0, fonte="html-media-element")},
        dinamicos_frescos=False,
    )
    sessao = fundir([parado, smtc(currentTime=350.0)])

    assert sessao.currentTime.value == 350.0
    assert sessao.currentTime.source == "smtc"


def test_a_fonte_velha_ainda_responde_pelo_nome_da_obra():
    """A assimetria que importa: um `currentTime` de um minuto atrás está
    errado agora; o nome da obra de um minuto atrás continua sendo o nome."""
    velha = Leitura(
        "provider-adapter",
        {
            "workTitle": campo("O Rei", fonte="provider-adapter"),
            "currentTime": campo(10.0, fonte="provider-adapter"),
        },
        dinamicos_frescos=False,
    )
    sessao = fundir([velha])

    assert sessao.workTitle.value == "O Rei"
    assert sessao.currentTime.value is None


def test_todas_as_fontes_velhas_deixam_o_tempo_ausente_em_vez_de_antigo():
    """Não há "melhor palpite" para tempo. Um número velho na tela é pior do que
    nenhum: ele parece medido."""
    sessao = fundir([
        Leitura("html-media-element", {"currentTime": campo(10.0)}, dinamicos_frescos=False),
        Leitura("smtc", {"currentTime": campo(20.0)}, dinamicos_frescos=False),
    ])

    assert sessao.currentTime.value is None
    assert sessao.currentTime.source is None


# ── As proibições ─────────────────────────────────────────────────────────


def test_a_ordem_de_chegada_nao_decide_nada():
    """"Último evento vence" e "última fonte registrada vence" são as duas
    primeiras proibições da fase. Inverter a lista não pode mudar a resposta."""
    fontes = [smtc(playbackState="playing"), video(playbackState="paused")]

    assert fundir(fontes).playbackState == fundir(list(reversed(fontes))).playbackState


def test_nenhuma_fonte_ganha_a_sessao_inteira():
    """A proibição nº 5 do Master Loop. A SMTC responde bem sobre tempo e isso
    NÃO lhe dá o direito de nomear a obra."""
    sessao = fundir([
        smtc(currentTime=90.0, duration=3600.0, workTitle="Google Chrome"),
        Leitura("provider-adapter", {
            "workTitle": campo("O Justiceiro", fonte="provider-adapter"),
        }),
    ])

    assert sessao.currentTime.source == "smtc"
    assert sessao.workTitle.source == "provider-adapter"


def test_uma_fonte_fora_da_tabela_nao_preenche_o_campo():
    """A trava é estrutural: não adianta a janela declarar um `currentTime`
    perfeito. Ela não está na lista, e por isso não escreve ali."""
    sessao = fundir([
        Leitura("window-title", {"currentTime": campo(123.0, fonte="window-title")}),
    ])

    assert sessao.currentTime.value is None


def test_valor_sem_autoridade_nao_entra_mesmo_sendo_o_unico():
    """Um campo `trustworthy=False` é a fonte dizendo "tenho isto, mas não
    respondo por ele". Aceitar na falta de coisa melhor é como o nome do
    episódio virou o nome da obra no histórico."""
    sessao = fundir([Leitura("window-title", {"workTitle": campo("Netflix", confiavel=False)})])

    assert sessao.workTitle.value is None


def test_a_mesma_fonte_duas_vezes_e_atualizacao_e_nao_disputa():
    sessao = fundir([video(currentTime=10.0), video(currentTime=20.0)])

    assert sessao.currentTime.value == 20.0


# ── Determinismo e diagnóstico ────────────────────────────────────────────


def test_sem_fonte_nenhuma_a_sessao_sai_vazia_sem_estourar():
    sessao = fundir([])

    assert sessao == SessaoCanonica.vazia()


def test_a_procedencia_responde_de_onde_veio_cada_campo():
    """É o que transforma "o título está errado" em "o título veio da janela"."""
    sessao = fundir([
        smtc(currentTime=90.0),
        Leitura("window-title", {"workTitle": campo("O Justiceiro", fonte="window-title")}),
    ])

    procedencia = sessao.procedencia()
    assert procedencia["currentTime"] == "smtc"
    assert procedencia["workTitle"] == "window-title"
    assert procedencia["episodeTitle"] is None


@pytest.mark.parametrize("repeticao", range(3))
def test_as_mesmas_entradas_dao_sempre_a_mesma_saida(repeticao):
    leituras = [
        smtc(playbackState="playing", workTitle="Google Chrome", currentTime=5.0),
        video(playbackState="paused", currentTime=7.0),
        Leitura("window-title", {"workTitle": campo("O Rei", fonte="window-title")}),
    ]

    assert fundir(leituras) == fundir(leituras)
