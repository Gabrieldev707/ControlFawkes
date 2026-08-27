"""Obra e episódio na MESMA string, quando um serviço escreve assim.

## Correção de honestidade, 26/08/2026

A versão anterior deste arquivo abria com "Medido em 26/08/2026, contra os
formatos reais" e listava dois exemplos:

    "Prime Video: Invincible - S1 E4 - Neil Armstrong"
    "Demolidor: Renascido - T1 E5 - Com Sangue | Disney+"

**Nenhum dos dois foi medido. Os dois foram inventados.**

A medição de verdade, feita depois com uma sonda de DOM no console, com Gavião
Arqueiro tocando:

    document.title            "Gavião Arqueiro | Disney+"
    navigator.mediaSession    vazio, playbackState "none"

Só a obra. Sem temporada, sem episódio, sem separador — em lugar nenhum do
título nem da metadata declarada. O formato testado aqui não existe no Disney+,
e o teste verde em cima dele deu a confiança falsa de que o serviço estava
coberto enquanto ele gravava série sem T e sem E. Um teste verde sobre um
formato inventado é pior do que teste nenhum.

O Disney+ passou a ser atendido por adapter, que lê o Shadow DOM do player
(`browser-extension/src/content/providers/disney.js`), e o caso real dele vive
em `disney.test.ts`, contra o DOM medido.

## O que este arquivo continua provando, e por que fica

A separação em si — "obra + marcador + nome do episódio" numa string só — é
regra genérica do backend e vale para qualquer serviço que escreva assim. As
entradas abaixo são exemplos SINTÉTICOS do parser, e não afirmação sobre o
formato de nenhum serviço. Elas guardam o defeito de origem, que era real: o
marcador ficava DENTRO do nome da obra, e o estrago era triplo — uma linha de
histórico por episódio, nenhum pôster (o catálogo não conhece "Invincible - S1
E4 - Neil Armstrong") e nenhum T/E, que estavam escritos ali e eram jogados
fora.

É o mesmo defeito do "sherlock season 2" numa terceira forma. As duas
anteriores eram a temporada no fim e no meio; esta é a temporada COM o nome do
episódio depois dela.

O Prime Video segue **sem medição**. Não se sabe se ele escreve episódio no
título, e este arquivo não é evidência de que sim.
"""

from __future__ import annotations

import pytest

from app.bridge.estado import EstadoDaPonte
from app.bridge.eventos import validar
from app.history.recorder import HistoryRecorder
from app.history.store import HistoryStore
from app.media.fusao import fundir_com_a_ponte
from app.media.identidade import separar_obra_e_episodio
from app.media.now_playing import limpar_titulo_de_janela


@pytest.fixture
def store(tmp_path) -> HistoryStore:
    return HistoryStore(tmp_path / "historico.json")


# ── A separação, isolada ──────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("titulo", "obra", "episodio"),
    [
        ("Invincible - S1 E4 - Neil Armstrong", "Invincible", "T1 E4 · Neil Armstrong"),
        (
            "Demolidor: Renascido - T1 E5 - Com Sangue",
            "Demolidor: Renascido",
            "T1 E5 · Com Sangue",
        ),
        ("Loki | T1:E4 | Alguma Coisa", "Loki", "T1 E4 · Alguma Coisa"),
        ("Rick and Morty • 1x04 • M. Night Shaym", "Rick and Morty", "T1 E4 · M. Night Shaym"),
    ],
)
def test_a_obra_se_separa_do_episodio(titulo, obra, episodio):
    assert separar_obra_e_episodio(titulo) == (obra, episodio)


@pytest.mark.parametrize(
    "titulo",
    [
        # Sem marcador nenhum: a maioria dos títulos.
        "Duna: Parte Dois",
        "Batman: Caped Crusader",
        "46 Long",
        # Marcador NO FIM, sem nada depois. Aqui o que vem antes tanto pode ser
        # a obra quanto o episódio — é exatamente o que o Max faz —, e chutar
        # poria o nome de um episódio na linha da obra.
        "Ozymandias • T5 E14",
        "Invincible - S1 E4",
        # Números fora de faixa não são temporada nem episódio.
        "Alguma Coisa - S0 E0 - Nada",
        "",
    ],
)
def test_o_que_nao_da_para_separar_fica_inteiro(titulo):
    assert separar_obra_e_episodio(titulo) is None


def test_o_limpador_devolve_so_a_obra():
    """É o que impede uma linha de histórico por episódio."""
    limpo = limpar_titulo_de_janela(
        "Prime Video: Invincible - S1 E4 - Neil Armstrong - Google Chrome",
    )

    assert limpo == "Invincible"


def test_titulos_sem_marcador_continuam_intactos():
    """A regressão proibida: um subtítulo legítimo não é um episódio."""
    assert limpar_titulo_de_janela("Duna: Parte Dois - Netflix") == "Duna: Parte Dois"
    assert limpar_titulo_de_janela(
        "Prime Video: Batman: Caped Crusader",
    ) == "Batman: Caped Crusader"


# ── Pela ponte, que é o caminho de quem não tem adapter ───────────────────

def ponte(provider: str, titulo: str) -> EstadoDaPonte:
    estado = EstadoDaPonte()
    estado.registrar(
        validar({
            "protocolVersion": 1, "messageType": "POSITION_SYNC", "timestamp": 0.0,
            "payload": {
                "sessionId": "s1", "provider": provider, "playbackState": "playing",
                "currentTime": 600.0, "duration": 2880.0, "documentTitle": titulo,
            },
        }, agora=1000.0),
        agora=0.0,
    )
    return estado


@pytest.mark.parametrize(
    ("provider", "titulo", "obra", "episodio"),
    [
        (
            "www.primevideo.com",
            "Prime Video: Invincible - S1 E4 - Neil Armstrong",
            "Invincible",
            "T1 E4 · Neil Armstrong",
        ),
        (
            "www.disneyplus.com",
            "Demolidor: Renascido - T1 E5 - Com Sangue | Disney+",
            "Demolidor: Renascido",
            "T1 E5 · Com Sangue",
        ),
    ],
)
def test_o_episodio_chega_sem_adapter(provider, titulo, obra, episodio):
    """Um serviço que ESCREVA assim no título é atendido sem adapter.

    Títulos sintéticos, não medidos — ver o cabeçalho. O que se prova aqui é
    que a fusão aproveita o marcador quando ele existe na string, e não que
    Prime ou Disney+ o escrevam. O Disney+, medido, não escreve: ele publica
    "Gavião Arqueiro | Disney+" e nada mais, e por isso ganhou adapter.
    """
    lida = fundir_com_a_ponte(None, ponte(provider, titulo), agora=0.0)

    assert lida.title == obra
    assert lida.episode == episodio


def test_a_serie_vira_UMA_linha_e_nao_uma_por_episodio(store: HistoryStore):
    """O estrago principal: cada episódio abria uma linha nova.

    "Invincible - S1 E4 - Neil Armstrong" e "Invincible - S1 E5 - ..." são
    títulos diferentes, então eram obras diferentes — sem pôster nenhuma.
    """
    gravador = HistoryRecorder(store)
    episodios = [
        "Prime Video: Invincible - S1 E4 - Neil Armstrong",
        "Prime Video: Invincible - S1 E5 - That Actually Hurt",
        "Prime Video: Invincible - S1 E6 - You Look Kinda Dead",
    ]

    for titulo in episodios:
        estado = ponte("www.primevideo.com", titulo)
        for _ in range(200):
            gravador.observar(
                fundir_com_a_ponte(None, estado, agora=0.0), 1.0, "ASSISTINDO",
            )
    gravador.encerrar()

    itens = store.listar()
    assert len(itens) == 1
    assert itens[0].titulo == "Invincible"
    # E o último episódio é o que fica, com os números legíveis pela tela.
    assert itens[0].como_obra()["episodio"] == "T1 E6"


def test_o_max_continua_sem_virar_obra(store: HistoryStore):
    """O Max publica o episódio no começo e nada depois.

    Separar ali poria "46 Long" na linha da obra — o defeito que
    `PLATAFORMAS_COM_OBRA_NA_JANELA` existe para impedir.
    """
    gravador = HistoryRecorder(store)
    estado = ponte("play.hbomax.com", "⁨46 Long⁩ • HBO Max")

    for _ in range(300):
        gravador.observar(fundir_com_a_ponte(None, estado, agora=0.0), 1.0, "ASSISTINDO")
    gravador.encerrar()

    assert store.listar() == []
