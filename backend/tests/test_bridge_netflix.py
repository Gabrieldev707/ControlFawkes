"""Fase 10 — o adapter da Netflix chegando ao resto do sistema.

Gate: **"Netflix fornece metadata sem depender da SMTC para nome da obra."**

O teste do adapter em si (o DOM, os padrões, a cascata) vive em
`browser-extension/src/content/providers/netflix.test.ts`, junto do arquivo que
ele exercita. Aqui é a outra ponta: o que a página declarou vira o nome da obra
no cartão e no histórico — e vence a SMTC ao fazê-lo.
"""

from __future__ import annotations

import pytest

from app.bridge.estado import EstadoDaPonte
from app.bridge.eventos import validar
from app.history.recorder import HistoryRecorder
from app.history.store import HistoryStore
from dataclasses import replace

from app.media.fusao import fundir_com_a_ponte
from app.media.now_playing import NowPlaying


@pytest.fixture
def store(tmp_path) -> HistoryStore:
    return HistoryStore(tmp_path / "historico.json")


def mensagem(**payload: object) -> dict:
    base: dict = {
        "sessionId": "sessao-1",
        "provider": "www.netflix.com",
        "playbackState": "playing",
        "currentTime": 100.0,
        "duration": 3238.0,
    }
    base.update(payload)
    return {
        "protocolVersion": 1,
        "messageType": "POSITION_SYNC",
        "timestamp": 0.0,
        "payload": base,
    }


def com_metadata(**payload: object) -> EstadoDaPonte:
    estado = EstadoDaPonte()
    evento = validar(mensagem(**payload), agora=1000.0)
    assert not hasattr(evento, "code"), evento
    estado.registrar(evento, agora=0.0)
    return estado


def netflix_cega(**overrides: object) -> NowPlaying:
    """A leitura do Windows na Netflix: as duas fontes dizendo "Netflix".

    Medido, e é o estado normal: a SMTC do Chrome publica o nome do site e a
    janela em `/watch` publica "Netflix - Google Chrome". Nenhuma das duas sabe
    o que está tocando.
    """
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


# ── Validação da metadata que chega ───────────────────────────────────────

def test_a_metadata_do_adapter_e_validada_como_qualquer_entrada():
    evento = validar(
        mensagem(workTitle="  Sherlock  ", seasonNumber=2, episodeNumber=1), 1000.0,
    )

    assert evento.workTitle == "Sherlock"
    assert evento.seasonNumber == 2
    assert evento.episodeNumber == 1


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        # Vazio é ausente, não uma obra chamada "".
        ("workTitle", "   "),
        ("workTitle", 42),
        # Zero não existe em nenhuma das duas contagens.
        ("seasonNumber", 0),
        ("episodeNumber", 0),
        # Ano não é temporada.
        ("seasonNumber", 1985),
        # `True` é `int` em Python, e viraria temporada 1 sem a checagem.
        ("seasonNumber", True),
        ("episodeNumber", "1"),
    ],
)
def test_metadata_impossivel_vira_ausente(campo, valor):
    evento = validar(mensagem(**{campo: valor}), 1000.0)

    assert getattr(evento, campo) is None


def test_texto_gigante_e_cortado_e_nao_recusa_a_mensagem():
    """Um DOM hostil pode devolver o documento inteiro como `textContent`.

    Cortar em vez de recusar: o resto da mensagem continua valendo, e um nome
    truncado ainda é melhor do que nenhum.
    """
    evento = validar(mensagem(workTitle="a" * 5000), 1000.0)

    assert len(evento.workTitle) == 300
    assert evento.currentTime == 100.0


# ── O gate ────────────────────────────────────────────────────────────────

def test_a_netflix_ganha_nome_sem_a_smtc():
    """A frase literal do gate.

    A SMTC diz "Netflix". A janela diz "Netflix". A página diz "Sherlock" — e é
    a página que vence, porque ela é a única que sabe.
    """
    estado = com_metadata(workTitle="Sherlock", episodeTitle="Um Escândalo em Belgravia",
                          seasonNumber=2, episodeNumber=1)

    fundida = fundir_com_a_ponte(netflix_cega(), estado, agora=0.0)

    assert fundida.title == "Sherlock"
    # E o nome passa a ser o da OBRA, não um palpite: quem o disse lê a página.
    assert fundida.trustworthy is True


def test_o_episodio_chega_com_os_numeros():
    """"continuar assistindo não fala o ep que to" — era isto.

    O formato "T2 E1" não é decorativo: `como_temporada_e_episodio` o lê para
    montar a linha da tela de perfil.
    """
    estado = com_metadata(workTitle="Sherlock", episodeTitle="Um Escândalo em Belgravia",
                          seasonNumber=2, episodeNumber=1)

    fundida = fundir_com_a_ponte(netflix_cega(), estado, agora=0.0)

    assert fundida.episode == "T2 E1 · Um Escândalo em Belgravia"


def test_sem_numeros_o_nome_do_episodio_ainda_vale():
    estado = com_metadata(workTitle="Sherlock", episodeTitle="Um Escândalo em Belgravia")

    fundida = fundir_com_a_ponte(netflix_cega(), estado, agora=0.0)

    assert fundida.episode == "Um Escândalo em Belgravia"


def test_so_os_numeros_tambem_valem():
    estado = com_metadata(workTitle="Sherlock", seasonNumber=2, episodeNumber=1)

    fundida = fundir_com_a_ponte(netflix_cega(), estado, agora=0.0)

    assert fundida.episode == "T2 E1"


def test_filme_nao_ganha_episodio_inventado():
    estado = com_metadata(workTitle="Duna: Parte Dois")

    fundida = fundir_com_a_ponte(netflix_cega(), estado, agora=0.0)

    assert fundida.title == "Duna: Parte Dois"
    assert fundida.episode is None


def test_o_nome_sobrevive_ao_tempo_envelhecer():
    """A assimetria da Fase 8, com consequência prática.

    A aba parou de mandar posição. O TEMPO dela sai da disputa; o NOME não —
    o nome da obra de um minuto atrás continua sendo o nome da obra.
    """
    from app.bridge.estado import SEGUNDOS_ATE_O_TEMPO_ENVELHECER

    estado = com_metadata(workTitle="Sherlock", currentTime=2974.0)

    fundida = fundir_com_a_ponte(
        netflix_cega(position_seconds=10.0),
        estado,
        agora=SEGUNDOS_ATE_O_TEMPO_ENVELHECER + 5,
    )

    assert fundida.title == "Sherlock"
    # E o tempo voltou a ser o da SMTC, que é o que a Fase 8 manda.
    assert fundida.position_seconds == 10.0


def test_o_adapter_de_outro_servico_nao_renomeia_a_sessao():
    """Uma aba da Netflix atrás não nomeia o que toca no Prime Video."""
    estado = com_metadata(workTitle="Sherlock")

    fundida = fundir_com_a_ponte(
        netflix_cega(platform="PRIME_VIDEO", title="Invincible", trustworthy=True),
        estado,
        agora=0.0,
    )

    assert fundida.title == "Invincible"


# ── O que o usuário reclamou, ponta a ponta ───────────────────────────────

def test_a_netflix_finalmente_entra_no_historico(store: HistoryStore):
    """"netflix nao ta salvando ainda".

    No `historico.json` real deste computador havia UMA linha de Netflix, de
    13/08/2026: `NETFLIX::netflix`, 120 segundos — a página de catálogo. Nada
    mais, nunca, porque `_titulo_generico("Netflix")` zerava o título e o
    gravador descartava a sessão inteira.
    """
    estado = com_metadata(workTitle="Sherlock", episodeTitle="Um Escândalo em Belgravia",
                          seasonNumber=2, episodeNumber=1)
    gravador = HistoryRecorder(store)

    for _ in range(400):
        fundida = fundir_com_a_ponte(netflix_cega(), estado, agora=0.0)
        gravador.observar(fundida, 1.0, "ASSISTINDO")
    gravador.encerrar()

    [item] = store.listar()
    assert item.titulo == "Sherlock"
    assert item.platform == "NETFLIX"
    # A chave é a da OBRA — a série não vira uma linha por episódio.
    assert item.chave == "NETFLIX::sherlock"
    # E a tela de perfil consegue ler os números de volta.
    assert item.como_obra()["episodio"] == "T2 E1"


def test_sem_o_adapter_a_netflix_continua_invisivel(store: HistoryStore):
    """O par do teste acima. Sem ele, "sempre grava" também passaria — e o
    ponto é que era o ADAPTER que faltava, não outra coisa."""
    gravador = HistoryRecorder(store)

    for _ in range(400):
        fundida = fundir_com_a_ponte(netflix_cega(), EstadoDaPonte(), agora=0.0)
        gravador.observar(fundida, 1.0, "ASSISTINDO")
    gravador.encerrar()

    assert store.listar() == []


# ── O fim de uma reprodução, dito pelo <video> ────────────────────────────

def test_o_filme_terminado_sai_de_continuar_assistindo(store: HistoryStore):
    """"filmes que ja terminei nao sai dai, ele so fala faltam x horas".

    A razão posição/duração quase nunca chega a 0,94: a última posição gravada
    é a de alguns segundos antes do fim, e no fim o player pula para a tela
    seguinte, onde a posição é outra coisa. Medido no histórico real —
    `spider-noir` com 7647 segundos assistidos e `posicao 0.016`.

    O `ended` do `<video>` é a evidência DIRETA, e a SMTC não a tem: ela publica
    "pausado", que é o que um filme no meio também é.
    """
    gravador = HistoryRecorder(store)
    tocando = netflix_cega(
        title="Duna", trustworthy=True, position_seconds=100.0, duration_seconds=7000.0,
    )

    for _ in range(200):
        gravador.observar(tocando, 1.0, "ASSISTINDO")
    # O `<video>` acabou. A posição continua longe do fim, de propósito.
    gravador.observar(replace(tocando, ended=True, playing=False), 1.0, "ASSISTINDO")
    gravador.encerrar()

    [item] = store.listar()
    assert item.concluida is True
    assert item.terminado is True
    assert store.continuar() == []


def test_assistir_de_novo_traz_o_filme_de_volta(store: HistoryStore):
    """O par: "concluída" não é para sempre.

    Uma reprodução nova começa não-concluída, e é isso que faz o filme voltar à
    lista sem ninguém precisar mexer em nada.
    """
    gravador = HistoryRecorder(store)
    tocando = netflix_cega(
        title="Duna", trustworthy=True, position_seconds=6900.0, duration_seconds=7000.0,
    )
    for _ in range(200):
        gravador.observar(tocando, 1.0, "ASSISTINDO")
    gravador.observar(replace(tocando, ended=True), 1.0, "ASSISTINDO")
    gravador.encerrar()
    assert store.continuar() == []

    # De novo, do começo — outra duração para ser outra reprodução.
    de_novo = replace(tocando, position_seconds=30.0, duration_seconds=7001.0, ended=False)
    outro = HistoryRecorder(store)
    for _ in range(200):
        outro.observar(de_novo, 1.0, "ASSISTINDO")
    outro.encerrar()

    assert [i.titulo for i in store.continuar()] == ["Duna"]


def test_a_serie_mostra_onde_a_pessoa_parou_no_episodio(store: HistoryStore):
    """"continuar assistindo, ex: invecible nao mostra onde parei".

    A linha é multi-reprodução, então `posicao` e `duracao` saem de cena como
    resposta sobre a OBRA — o conserto do Batman, que continua de pé. O que
    mudou é que eles não são mais jogados fora: voltam com o nome do que de fato
    descrevem, e a tela os rotula como do episódio.
    """
    # A posição vem da PONTE, que é quem mede dentro da página — a da SMTC
    # perderia esta disputa, e é justamente esse o conserto da Fase 8.
    estado = com_metadata(
        workTitle="Invincible", seasonNumber=1, episodeNumber=4,
        currentTime=2228.0, duration=2921.0,
    )
    gravador = HistoryRecorder(store)

    for _ in range(200):
        fundida = fundir_com_a_ponte(
            netflix_cega(platform="NETFLIX"), estado, agora=0.0,
        )
        gravador.observar(fundida, 1.0, "ASSISTINDO")
    gravador.encerrar()

    [item] = store.listar()
    obra = item.como_obra()
    # A obra segue sem posição: ela não tem duração, e inventar uma é o bug.
    assert obra["posicao"] is None and obra["duracao"] is None
    # Mas "onde parei" tem resposta, e ela é do EPISÓDIO.
    assert obra["posicaoDoEpisodio"] == 2228.0
    assert obra["duracaoDoEpisodio"] == 2921.0
    assert obra["episodio"] == "T1 E4"


# ── Duas abas tocando: o que travava a Netflix ────────────────────────────

def _com_youtube_junto(**netflix_payload: object) -> EstadoDaPonte:
    """Netflix e YouTube tocando ao mesmo tempo, o YouTube falando por último.

    É o estado real medido: 15 das 16 observações do dataset da Fase 14 são
    `duas-tocando`.
    """
    estado = EstadoDaPonte()
    nf = {"sessionId": "netflix", "provider": "www.netflix.com"}
    nf.update(netflix_payload)
    estado.registrar(validar(mensagem(**nf), 1000.0), agora=0.0)
    estado.registrar(
        validar(
            mensagem(
                sessionId="youtube", provider="www.youtube.com",
                playbackState="playing", currentTime=42.0, duration=600.0,
            ),
            1000.0,
        ),
        # Depois da Netflix: no desempate global, ele vence.
        agora=1.0,
    )
    return estado


def test_o_youtube_tocando_junto_nao_rouba_a_netflix():
    """O bug medido em 25/08/2026: tocava no cartão e não gravava.

    `estado.atual()` devolve o vencedor GLOBAL, e com duas abas tocando ele
    alterna a cada batimento. Quando calhava de ser o YouTube, a fusão não
    casava com a Netflix e o título voltava a ser "Netflix".
    """
    estado = _com_youtube_junto(workTitle="Spider-Man: Across the Spider-Verse")

    # As duas sessões estão vivas e o YouTube é quem está tocando — sem isso o
    # teste não exercitaria conflito nenhum.
    #
    # (O vencedor GLOBAL deixou de ser o YouTube em 26/08, quando saber nomear
    # a obra entrou no desempate. O que este teste prova continua sendo outra
    # coisa: perguntar pelo serviço certo não depende de quem vence no geral.)
    vivas = {s.platform: s for s in estado.vivas(agora=1.0)}
    assert set(vivas) == {"NETFLIX", "YOUTUBE"}
    assert vivas["YOUTUBE"].tocando

    fundida = fundir_com_a_ponte(netflix_cega(), estado, agora=1.0)

    assert fundida.title == "Spider-Man: Across the Spider-Verse"
    assert fundida.trustworthy is True


def test_o_tempo_da_netflix_nao_vem_da_aba_do_youtube():
    """O outro lado do mesmo erro, e o mais perigoso.

    O `currentTime` do YouTube cabe na duração do filme e pareceria plausível.
    """
    estado = _com_youtube_junto(
        workTitle="Spider-Man: Across the Spider-Verse",
        currentTime=3600.0, duration=8400.0,
    )

    fundida = fundir_com_a_ponte(netflix_cega(), estado, agora=1.0)

    assert fundida.position_seconds == pytest.approx(3601.0)
    assert fundida.duration_seconds == pytest.approx(8400.0)


def test_o_filme_entra_no_historico_com_o_youtube_tocando_junto(store: HistoryStore):
    """A prova de ponta a ponta: com o YouTube junto, o filme GRAVA.

    Sem o conserto, o título alternava entre o nome do filme e "Netflix"
    (genérico, descartado), e cada alternância zerava o acumulado — um filme
    inteiro nunca alcançava os 90 segundos que o histórico exige.
    """
    estado = _com_youtube_junto(
        workTitle="Spider-Man: Across the Spider-Verse",
        currentTime=3600.0, duration=8400.0,
    )
    gravador = HistoryRecorder(store)

    for _ in range(400):
        gravador.observar(
            fundir_com_a_ponte(netflix_cega(), estado, agora=1.0), 1.0, "ASSISTINDO",
        )
    gravador.encerrar()

    [item] = store.listar()
    assert item.titulo == "Spider-Man: Across the Spider-Verse"
    assert item.platform == "NETFLIX"
    # E "faltam x" tem resposta: é filme, uma reprodução só.
    assert item.multiplas_reproducoes is False
    # 3601 e não 3600: um segundo de extrapolação desde o batimento, que é o
    # comportamento da Fase 8 e não um arredondamento.
    assert item.posicao == pytest.approx(3601.0)
    assert item.duracao == pytest.approx(8400.0)


def test_uma_piscada_na_leitura_nao_joga_fora_a_sessao(store: HistoryStore):
    """A leitura pisca: a SMTC passa uma volta, a janela muda de título.

    Sem tolerância, cada piscada zerava o acumulado, e uma sessão que pisca a
    cada poucos segundos nunca alcançava os 90 segundos.
    """
    estado = com_metadata(workTitle="Duna", currentTime=100.0, duration=8400.0)
    gravador = HistoryRecorder(store)

    for volta in range(400):
        # Uma piscada a cada 20 voltas: a leitura não sabe dizer o que toca.
        if volta % 20 == 19:
            gravador.observar(None, 1.0, "ASSISTINDO")
            continue
        gravador.observar(
            fundir_com_a_ponte(netflix_cega(), estado, agora=0.0), 1.0, "ASSISTINDO",
        )
    gravador.encerrar()

    [item] = store.listar()
    assert item.titulo == "Duna"


def test_a_troca_de_obra_de_verdade_continua_fechando_a_conta(store: HistoryStore):
    """O par: a tolerância não pode virar "nunca troca de obra".

    Oito segundos é mais que qualquer piscada e bem menos que o tempo de trocar
    de filme de propósito.
    """
    gravador = HistoryRecorder(store)
    um = com_metadata(workTitle="Duna", currentTime=100.0, duration=8400.0)
    outro = com_metadata(workTitle="Blade Runner", currentTime=50.0, duration=9000.0)

    for _ in range(200):
        gravador.observar(fundir_com_a_ponte(netflix_cega(), um, agora=0.0), 1.0, "ASSISTINDO")
    # Some por bem mais que a tolerância.
    for _ in range(30):
        gravador.observar(None, 1.0, "ASSISTINDO")
    for _ in range(200):
        gravador.observar(fundir_com_a_ponte(netflix_cega(), outro, agora=0.0), 1.0, "ASSISTINDO")
    gravador.encerrar()

    assert sorted(i.titulo for i in store.listar()) == ["Blade Runner", "Duna"]


# ── A Netflix pela JANELA, sem extensão nenhuma ───────────────────────────

def test_a_janela_da_netflix_nomeia_a_obra_na_pagina_de_reproducao():
    """A medição de 25/08/2026 que corrigiu a regra antiga.

    A regra dizia "Netflix — nada, nunca o conteúdo", e isso era verdade da
    página de CATÁLOGO. Com o filme tocando, a janela publica a obra.
    """
    from app.media.now_playing import da_janela

    lida = da_janela(
        "Spider-Man: Across the Spider-Verse - Netflix - Google Chrome",
        "NETFLIX",
        tocando=True,
    )

    assert lida.title == "Spider-Man: Across the Spider-Verse"
    assert lida.trustworthy is True


@pytest.mark.parametrize(
    "janela",
    [
        "Netflix - Google Chrome",
        "Netflix - Home - Netflix",
        "Home - Netflix - Google Chrome",
        "Minha lista - Netflix - Google Chrome",
        "netflix.com",
    ],
)
def test_o_catalogo_da_netflix_continua_barrado(janela, store: HistoryStore):
    """O que protegia a regra antiga continua de pé, e antes daqui.

    `_titulo_generico` barra a home, as seções do menu e endereços crus. A
    página de catálogo nunca alcança o booleano de confiança — foi por isso que
    trocá-lo é seguro.
    """
    from app.media.now_playing import da_janela

    gravador = HistoryRecorder(store)
    lida = da_janela(janela, "NETFLIX", tocando=True)

    for _ in range(400):
        gravador.observar(lida, 1.0, "ASSISTINDO")
    gravador.encerrar()

    assert store.listar() == []


def test_a_netflix_grava_sem_extensao_nenhuma(store: HistoryStore):
    """O conserto que não depende do navegador cooperar.

    Era ESTA a razão de a Netflix nunca ter entrado no histórico — e não a
    falta do adapter. O nome estava certo na janela, `limpar_titulo_de_janela`
    já o extraía, e ele era jogado fora porque `trustworthy` vinha falso.
    """
    from app.media.now_playing import da_janela

    gravador = HistoryRecorder(store)
    lida = da_janela(
        "Spider-Man: Across the Spider-Verse - Netflix - Google Chrome",
        "NETFLIX",
        tocando=True,
    )

    for _ in range(400):
        gravador.observar(lida, 1.0, "ASSISTINDO")
    gravador.encerrar()

    [item] = store.listar()
    assert item.titulo == "Spider-Man: Across the Spider-Verse"
    assert item.platform == "NETFLIX"


def test_o_max_continua_sem_inventar_obra(store: HistoryStore):
    """A regressão proibida: o Max nomeia o EPISÓDIO, e ele não vira obra.

    Era assim que "46 Long" e "Pilot" viravam títulos assistidos.
    """
    from app.media.now_playing import da_janela

    gravador = HistoryRecorder(store)
    lida = da_janela("⁨46 Long⁩ • HBO Max - Google Chrome", "MAX", tocando=True)

    for _ in range(400):
        gravador.observar(lida, 1.0, "ASSISTINDO")
    gravador.encerrar()

    assert store.listar() == []


# ── Temporada e episódio, só quando são conhecidos ────────────────────────

def test_o_episodio_sozinho_vira_numero_e_nao_nome():
    """A Netflix escreve "E1" quando já se sabe a temporada.

    Medido em 26/08/2026 com Breaking Bad: "E1" não casava com padrão nenhum e
    caía como NOME do episódio — perdendo as duas coisas de uma vez. O número
    não ficava estruturado, e o nome de verdade era descartado porque a vaga já
    estava ocupada.
    """
    estado = com_metadata(workTitle="Breaking Bad", episodeNumber=1, episodeTitle="Piloto")

    fundida = fundir_com_a_ponte(netflix_cega(), estado, agora=0.0)

    assert fundida.episode == "E1 · Piloto"


def test_a_temporada_nao_e_inventada_quando_falta():
    """Completar com "T1" erra justamente para quem está na quinta temporada."""
    estado = com_metadata(workTitle="Breaking Bad", episodeNumber=1)

    fundida = fundir_com_a_ponte(netflix_cega(), estado, agora=0.0)

    assert fundida.episode == "E1"
    assert "T" not in fundida.episode


def test_com_a_temporada_publicada_ela_aparece():
    estado = com_metadata(
        workTitle="Breaking Bad", seasonNumber=5, episodeNumber=14,
        episodeTitle="Ozymandias",
    )

    fundida = fundir_com_a_ponte(netflix_cega(), estado, agora=0.0)

    assert fundida.episode == "T5 E14 · Ozymandias"


def test_a_tela_de_perfil_le_a_forma_curta(store: HistoryStore):
    """`como_temporada_e_episodio` monta o rótulo do cartão de perfil.

    Ele precisa aceitar "E1" sozinho, senão o cartão mostraria o texto inteiro
    ("E1 · Piloto") no lugar de um rótulo curto.
    """
    estado = com_metadata(workTitle="Breaking Bad", episodeNumber=1, episodeTitle="Piloto")
    gravador = HistoryRecorder(store)

    for _ in range(400):
        gravador.observar(
            fundir_com_a_ponte(netflix_cega(), estado, agora=0.0), 1.0, "ASSISTINDO",
        )
    gravador.encerrar()

    [item] = store.listar()
    assert item.como_obra()["episodio"] == "E1"

