"""O histórico do que foi assistido, e o perfil que sai dele."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api import websocket as websocket_module
from app.history.recorder import SEGUNDOS_ENTRE_GRAVACOES, HistoryRecorder
from app.history.store import MAXIMO_DE_ITENS, Assistido, HistoryStore
from app.main import app
from app.media.now_playing import NowPlaying


def tocando(titulo: str, platform="NETFLIX", playing=True, posicao=None, duracao=None):
    return NowPlaying(
        title=titulo, artist=None, app="Chrome", platform=platform,
        playing=playing, position_seconds=posicao, duration_seconds=duracao,
        thumbnail=None,
    )


@pytest.fixture
def store(tmp_path: Path) -> HistoryStore:
    return HistoryStore(tmp_path / "historico.json")


# ── O que entra e o que não entra ─────────────────────────────────────────


def test_the_same_title_watched_twice_is_one_line_with_the_total(store: HistoryStore):
    """Meia hora hoje e meia amanhã são uma hora do mesmo filme."""
    store.registrar("Duna", "MAX", 1800, 1800, 9000, agora=1)
    store.registrar("duna", "MAX", 1800, 3600, 9000, agora=2)

    tudo = store.listar()

    assert len(tudo) == 1
    assert tudo[0].segundos == 3600
    assert tudo[0].posicao == 3600


def test_what_was_never_a_work_does_not_survive_in_the_file(store: HistoryStore):
    """Barrar na gravação não basta: o que entrou antes do filtro continua no
    arquivo. Medido no histórico real — uma linha "Netflix" de 120 segundos era
    a única com plataforma, e fazia a tela anunciar a Netflix como serviço mais
    usado enquanto 58 minutos de filme de verdade não contavam para nada."""
    store.registrar("Netflix", "NETFLIX", 120, None, None, agora=2)
    store.registrar("Batman: Caped Crusader", "PRIME_VIDEO", 3530, 480, 1680, agora=1)

    tudo = store.listar()

    assert [item.titulo for item in tudo] == ["Batman: Caped Crusader"]
    # E não aparece em "continuar assistindo", onde chegava em primeiro com a
    # capa de um título qualquer que o catálogo devolveu para a busca "Netflix".
    assert [item.titulo for item in store.continuar()] == ["Batman: Caped Crusader"]


def test_one_evening_is_one_day_even_after_nine_pm():
    """A conquista conta o dia do relógio de quem assiste, não o de Greenwich.

    Medido no histórico real: três títulos numa mesma noite de 13/08, dois deles
    depois das 21h. Em UTC isso vira 13 e 14, e "Constante" anunciava dois dias
    de uma noite só — inflando a única conquista que mede constância."""
    from datetime import datetime

    from app.history.achievements import calcular

    def as_horas(hora: int) -> float:
        return datetime(2026, 8, 13, hora, 30).timestamp()

    historico = [
        Assistido(
            chave=f"MAX::filme {hora}", titulo=f"Filme {hora}", platform="MAX",
            segundos=600, posicao=None, duracao=None, visto_em=as_horas(hora),
        )
        for hora in (18, 22, 23)
    ]

    constante = next(c for c in calcular(historico) if c.codigo == "CONSTANTE")

    assert constante.atual == 1


def test_music_is_controlled_but_never_counted_as_watched(store: HistoryStore):
    """O Spotify segue inteiro no controle e no cartão de "tocando agora" — o
    que ele não vira é histórico. Cada faixa passa dos 90 segundos, então uma
    tarde com música de fundo viraria dezenas de "títulos assistidos" e
    disputaria o "mais usado" com filme."""
    from app.history.recorder import HistoryRecorder

    gravador = HistoryRecorder(store)
    musica = NowPlaying(
        title="Verdade", artist="Zeca Pagodinho", app="Spotify", platform="SPOTIFY",
        playing=True, position_seconds=10.0, duration_seconds=258.0, thumbnail=None,
    )
    filme = NowPlaying(
        title="Duna", artist=None, app="chrome.exe", platform="MAX",
        playing=True, position_seconds=10.0, duration_seconds=9000.0, thumbnail=None,
    )

    for _ in range(200):
        gravador.observar(musica, 1.0)
    gravador.encerrar()
    for _ in range(200):
        gravador.observar(filme, 1.0)
    gravador.encerrar()

    assert [item.titulo for item in store.listar()] == ["Duna"]


def test_a_youtube_video_never_keeps_a_movie_poster(store: HistoryStore):
    """Todo pôster daqui veio do TMDB, que é catálogo de filme e série. Para o
    nome de um vídeo do YouTube ele devolve a capa de outra coisa — medido, o
    vlog "CHEGUEI NA SÍRIA..." apareceu em "continuar assistindo" com pôster de
    filme. Descartar na leitura tira da tela o que já ficou gravado."""
    store.registrar(
        "CHEGUEI NA SÍRIA", "YOUTUBE", 240, None, None,
        poster_url="https://image.tmdb.org/t/p/w342/filme-errado.jpg", agora=2,
    )
    store.registrar(
        "Batman: Caped Crusader", "PRIME_VIDEO", 3530, 480, 1680,
        poster_url="https://image.tmdb.org/t/p/w342/batman.jpg", agora=1,
    )

    capas = {item.titulo: item.poster_url for item in store.listar()}

    assert capas["CHEGUEI NA SÍRIA"] is None
    # E quem tem catálogo de verdade não perde a capa certa.
    assert capas["Batman: Caped Crusader"].endswith("/batman.jpg")


def test_a_wrong_poster_is_removed_from_the_file_and_not_just_hidden(
    store: HistoryStore,
):
    """Esconder na leitura não bastava, e o motivo é o enriquecimento.

    `_descobrir_capas` só pergunta ao catálogo por quem NÃO tem pôster. Com a
    capa errada gravada, o título parecia resolvido para sempre: a capa ficava
    escondida da tela e ao mesmo tempo ocupando o lugar da resposta certa. A
    poda tira do arquivo o que a leitura já recusava.
    """
    store.registrar(
        "CHEGUEI NA SÍRIA", "YOUTUBE", 240, None, None,
        poster_url="https://image.tmdb.org/t/p/w342/filme-errado.jpg", agora=3,
    )
    # A página de catálogo aberta, não uma obra — e com capa de um filme
    # qualquer que casou com a busca "Netflix".
    store.registrar(
        "Netflix", "NETFLIX", 120, None, None,
        poster_url="https://image.tmdb.org/t/p/w342/outro-filme.jpg", agora=2,
    )
    store.registrar(
        "Batman: Caped Crusader", "PRIME_VIDEO", 3530, 480, 1680,
        poster_url="https://image.tmdb.org/t/p/w342/batman.jpg", agora=1,
    )

    assert store.podar_capas() == 2

    # No ARQUIVO, e não só na leitura: é o arquivo que decide se o catálogo
    # será perguntado de novo.
    gravado = json.loads(store._caminho.read_text(encoding="utf-8"))
    capas = {linha["titulo"]: linha["posterUrl"] for linha in gravado.values()}
    assert capas["CHEGUEI NA SÍRIA"] is None
    assert capas["Netflix"] is None
    # A capa que o catálogo tinha como acertar não se mexe.
    assert capas["Batman: Caped Crusader"].endswith("/batman.jpg")

    # E o tempo assistido continua inteiro: ele foi medido de verdade.
    assert gravado["YOUTUBE::cheguei na siria"]["segundos"] == 240


def test_pruning_a_clean_history_changes_nothing(store: HistoryStore):
    """Roda a cada partida do servidor: reescrever o arquivo sem motivo é
    trocar um risco de escrita por nada."""
    store.registrar(
        "Batman: Caped Crusader", "PRIME_VIDEO", 3530, 480, 1680,
        poster_url="https://image.tmdb.org/t/p/w342/batman.jpg", agora=1,
    )
    antes = store._caminho.read_text(encoding="utf-8")

    assert store.podar_capas() == 0
    assert store._caminho.read_text(encoding="utf-8") == antes


def test_the_same_name_on_another_service_is_another_line(store: HistoryStore):
    store.registrar("O Justiceiro", "MAX", 600, None, None, agora=1)
    store.registrar("O Justiceiro", "DISNEY_PLUS", 600, None, None, agora=2)

    assert len(store.listar()) == 2


def test_what_reached_the_end_stops_being_something_to_continue(store: HistoryStore):
    store.registrar("Duna", "MAX", 9000, 8800, 9000, agora=1)
    store.registrar("Interestelar", "MAX", 600, 600, 9000, agora=2)

    assert [item.titulo for item in store.continuar()] == ["Interestelar"]


def test_live_content_never_counts_as_finished(store: HistoryStore):
    """Sem duração não há fim: transmissão ao vivo fica em "continuar"."""
    store.registrar("Jogo ao vivo", "YOUTUBE", 3000, 3000, None, agora=1)

    assert store.listar()[0].terminado is False


def test_the_history_does_not_grow_without_end(store: HistoryStore):
    for indice in range(MAXIMO_DE_ITENS + 20):
        store.registrar(f"Filme {indice}", "MAX", 200, None, None, agora=indice)

    guardados = store.listar()

    assert len(guardados) == MAXIMO_DE_ITENS
    # Some o mais antigo, nunca o mais recente.
    assert guardados[0].titulo == f"Filme {MAXIMO_DE_ITENS + 19}"


def test_a_corrupted_file_means_no_history_not_a_crash(tmp_path: Path):
    caminho = tmp_path / "historico.json"
    caminho.write_text("{isto não é json", encoding="utf-8")

    assert HistoryStore(caminho).listar() == []


def test_what_the_catalog_discovers_is_not_lost_on_the_next_update(store: HistoryStore):
    item = store.registrar("Duna", "MAX", 600, None, None, agora=1)
    store.enriquecer(item.chave, "https://poster.jpg", ("Ficção Científica",))

    store.registrar("Duna", "MAX", 600, None, None, agora=2)

    guardado = store.listar()[0]
    assert guardado.generos == ("Ficção Científica",)
    assert guardado.poster_url == "https://poster.jpg"


# ── O gravador, que conta os segundos ─────────────────────────────────────


def test_passing_through_a_title_does_not_enter_the_history(store: HistoryStore):
    """Trinta segundos é procurar, não assistir."""
    gravador = HistoryRecorder(store)

    for _ in range(30):
        gravador.observar(tocando("Trailer qualquer"), 1.0)
    gravador.encerrar()

    assert store.listar() == []


def test_what_was_really_watched_enters_when_it_ends(store: HistoryStore):
    gravador = HistoryRecorder(store)

    for _ in range(200):
        gravador.observar(tocando("Duna", posicao=200, duracao=9000), 1.0)
    # Trocar de título fecha a conta do anterior.
    gravador.observar(tocando("Outro filme"), 1.0)

    assert [item.titulo for item in store.listar()] == ["Duna"]
    assert store.listar()[0].segundos == pytest.approx(200, abs=2)


def test_paused_time_is_not_watched_time(store: HistoryStore):
    """Deixar a Netflix parada a tarde inteira não é assistir."""
    gravador = HistoryRecorder(store)

    for _ in range(120):
        gravador.observar(tocando("Duna", playing=True), 1.0)
    for _ in range(600):
        gravador.observar(tocando("Duna", playing=False), 1.0)
    gravador.encerrar()

    assert store.listar()[0].segundos == pytest.approx(120, abs=2)


def test_a_long_session_is_written_before_it_ends(store: HistoryStore):
    """Fechar o servidor no meio de um filme não pode apagar duas horas."""
    gravador = HistoryRecorder(store)

    for _ in range(int(SEGUNDOS_ENTRE_GRAVACOES) + 5):
        gravador.observar(tocando("Duna"), 1.0)

    # Sem nenhum encerramento explícito, já existe registro no disco.
    assert store.listar()[0].titulo == "Duna"


def test_nothing_playing_closes_the_account_of_what_was(store: HistoryStore):
    gravador = HistoryRecorder(store)

    for _ in range(150):
        gravador.observar(tocando("Duna"), 1.0)
    gravador.observar(None, 1.0)

    assert store.listar()[0].titulo == "Duna"


# ── A porta HTTP ──────────────────────────────────────────────────────────


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    from app.protocol.dispatcher import Dispatcher
    from app.security.device_store import DeviceStore
    from app.security.pairing import PairingService

    store = DeviceStore(
        filepath=tmp_path / "paired_devices.json",
        lockpath=tmp_path / "paired_devices.lock",
    )
    catalogo = Mock()
    catalogo.enabled = False
    dispatcher = Dispatcher(
        device_store=store,
        pairing_service=PairingService(store),
        history_recorder=HistoryRecorder(HistoryStore(tmp_path / "historico.json")),
        catalog=catalogo,
    )
    monkeypatch.setattr(websocket_module, "dispatcher", dispatcher)
    with TestClient(app) as cliente:
        cliente.dispatcher = dispatcher
        yield cliente


def credenciais(cliente) -> dict[str, str]:
    servico = cliente.dispatcher.pairing_service
    resultado = servico.attempt(servico.initialize(), "Celular")
    return {"X-Device-Id": resultado.device_id, "X-Device-Token": resultado.token}


def test_the_profile_needs_authentication(cliente):
    assert cliente.get("/profile").status_code == 401


def test_an_empty_history_is_a_valid_answer(cliente):
    resposta = cliente.get("/profile", headers=credenciais(cliente)).json()

    assert resposta["continuar"] == []
    assert resposta["totalDeTitulos"] == 0


def test_the_profile_adds_up_by_service_and_by_genre(cliente):
    store = cliente.dispatcher.history_recorder.store
    duna = store.registrar("Duna", "MAX", 3600, 100, 9000, agora=1)
    store.enriquecer(duna.chave, None, ("Ficção Científica", "Aventura"))
    justiceiro = store.registrar("O Justiceiro", "DISNEY_PLUS", 1800, 100, 3000, agora=2)
    store.enriquecer(justiceiro.chave, None, ("Ação", "Aventura"))

    resposta = cliente.get("/profile", headers=credenciais(cliente)).json()

    # Aventura aparece nos dois, então lidera somando os tempos.
    assert resposta["generos"][0] == {"nome": "Aventura", "segundos": 5400}
    assert resposta["plataformas"][0] == {"nome": "MAX", "segundos": 3600}
    assert resposta["totalDeSegundos"] == 5400
    assert [item["titulo"] for item in resposta["continuar"]] == ["O Justiceiro", "Duna"]


def test_recommendations_degrade_when_the_catalog_is_off(cliente):
    cliente.dispatcher.history_recorder.store.registrar("Duna", "MAX", 600, None, None)

    resposta = cliente.get("/profile/recommendations", headers=credenciais(cliente)).json()

    assert resposta == {"enabled": False, "base": None, "titles": []}


def test_the_history_can_be_erased(cliente):
    cabecalhos = credenciais(cliente)
    cliente.dispatcher.history_recorder.store.registrar("Duna", "MAX", 600, None, None)

    apagado = cliente.delete("/profile/history", headers=cabecalhos)

    assert apagado.status_code == 200
    assert cliente.get("/profile", headers=cabecalhos).json()["totalDeTitulos"] == 0


def test_the_history_is_recorded_even_with_no_phone_connected(store: HistoryStore):
    """Assistir não depende do controle estar aberto na mão.

    O laço pulava tudo quando ninguém estava autenticado, então o histórico só
    existia enquanto a página do celular estivesse aberta — justamente o momento
    em que a pessoa não está assistindo.
    """
    import asyncio
    from unittest.mock import AsyncMock

    from app.protocol.dispatcher import Dispatcher

    dispatcher = Dispatcher(history_recorder=HistoryRecorder(store))
    assert dispatcher._authenticated == {}

    leitura = tocando("Batman: Caped Crusader", "PRIME_VIDEO")
    dispatcher._leitura = AsyncMock()
    dispatcher._leitura.ler = AsyncMock(return_value=leitura)
    dispatcher._leitura.travada = False

    async def rodar():
        for _ in range(200):
            await dispatcher._read_now_playing(contar=True)

    asyncio.run(rodar())
    dispatcher.history_recorder.encerrar()

    assert [item.titulo for item in store.listar()] == ["Batman: Caped Crusader"]


def test_a_better_title_cleaner_merges_what_was_split_before(store: HistoryStore):
    """O passado não melhora sozinho quando a limpeza melhora.

    Aconteceu de verdade: "Prime Video: Batman" e "Batman" viraram duas linhas
    do mesmo filme, cada uma com um pedaço do tempo assistido.
    """
    from app.media.now_playing import limpar_titulo_de_janela

    store.registrar("Prime Video: Batman: Caped Crusader", "PRIME_VIDEO", 180, 180, None, agora=1)
    store.registrar("Batman: Caped Crusader", "PRIME_VIDEO", 120, 300, None, agora=2)
    assert len(store.listar()) == 2

    removidas = store.consolidar(limpar_titulo_de_janela)

    tudo = store.listar()
    assert removidas == 1
    assert [item.titulo for item in tudo] == ["Batman: Caped Crusader"]
    assert tudo[0].segundos == 300
    # A posição vem da leitura mais recente, não da soma.
    assert tudo[0].posicao == 300


def test_consolidating_a_clean_history_changes_nothing(store: HistoryStore):
    from app.media.now_playing import limpar_titulo_de_janela

    store.registrar("Duna", "MAX", 600, None, None, agora=1)
    store.registrar("Round 6", "NETFLIX", 600, None, None, agora=2)

    assert store.consolidar(limpar_titulo_de_janela) == 0
    assert len(store.listar()) == 2


def test_covers_are_discovered_even_when_the_recommendation_is_cached(cliente, monkeypatch):
    """A capa não pode ficar refém do cache das recomendações.

    Era o caso: com a resposta em cache, a função devolvia cedo e nenhum título
    novo ganhava imagem até o cache vencer, meia hora depois.
    """
    from unittest.mock import AsyncMock

    store = cliente.dispatcher.history_recorder.store
    catalogo = cliente.dispatcher.catalog
    catalogo.enabled = True
    catalogo.parecidos_com = AsyncMock(return_value=[])
    catalogo.detalhes_de = AsyncMock(return_value=("https://poster.jpg", ("Ação",)))

    cabecalhos = credenciais(cliente)
    store.registrar("Duna", "MAX", 3600, None, None, agora=1)
    cliente.get("/profile/recommendations", headers=cabecalhos)
    assert store.listar()[0].poster_url == "https://poster.jpg"

    # Agora o cache está quente. Um título novo ainda precisa ganhar capa.
    store.registrar("Round 6", "NETFLIX", 600, None, None, agora=2)
    catalogo.detalhes_de = AsyncMock(return_value=("https://round6.jpg", ("Drama",)))

    cliente.get("/profile/recommendations", headers=cabecalhos)

    capas = {item.titulo: item.poster_url for item in store.listar()}
    assert capas["Round 6"] == "https://round6.jpg"


def test_youtube_in_the_history_does_not_erase_the_recommendations(cliente):
    """Uma tarde de futebol ao vivo não pode apagar o bloco inteiro.

    Os serviços do histórico filtram as recomendações — a prova de quais a
    pessoa assina. Mas o TMDB não marca filme como assinatura do YouTube, então
    incluir o YouTube no filtro não estreita a lista: zera. Medido na tela, o
    "talvez você goste" sumiu no dia em que o histórico passou a reconhecer a
    plataforma do YouTube."""
    from unittest.mock import AsyncMock

    from app.api.profile import _cache

    # A resposta fica em cache por meia hora, num dicionário de módulo que
    # sobrevive entre testes: sem limpar, a chamada nem chega ao catálogo.
    _cache.clear()

    store = cliente.dispatcher.history_recorder.store
    catalogo = cliente.dispatcher.catalog
    catalogo.enabled = True
    catalogo.parecidos_com = AsyncMock(return_value=[])
    catalogo.detalhes_de = AsyncMock(return_value=(None, ()))

    store.registrar("Jogo ao vivo", "YOUTUBE", 600, None, None, agora=1)
    store.registrar("Duna", "MAX", 3600, None, None, agora=2)

    cliente.get("/profile/recommendations", headers=credenciais(cliente))

    plataformas = catalogo.parecidos_com.await_args.args[1]
    assert "YOUTUBE" not in plataformas
    assert plataformas == ["MAX"]


# ── Conquistas ────────────────────────────────────────────────────────────


def test_an_empty_history_unlocks_nothing_but_still_lists_everything(store: HistoryStore):
    """A grade precisa existir desde o começo: é ela que mostra o que dá para
    conquistar. Sem isso, quem nunca assistiu nada vê uma tela vazia."""
    from app.history.achievements import calcular, nivel

    conquistas = calcular([])

    assert len(conquistas) >= 10
    assert all(not c.conquistada for c in conquistas)
    assert nivel(conquistas)["nivel"] == 0


def test_watching_one_title_unlocks_the_first_play(store: HistoryStore):
    from app.history.achievements import calcular

    store.registrar("Duna", "MAX", 200, None, None, agora=1)

    conquistadas = {c.codigo for c in calcular(store.listar()) if c.conquistada}

    assert "PRIMEIRO_PLAY" in conquistadas
    assert "COLECIONADOR" not in conquistadas


def test_finishing_a_title_is_what_unlocks_the_finish_line(store: HistoryStore):
    from app.history.achievements import calcular

    store.registrar("Duna", "MAX", 9000, 8900, 9000, agora=1)

    conquistadas = {c.codigo for c in calcular(store.listar()) if c.conquistada}

    assert "ATE_O_FIM" in conquistadas


def test_progress_is_reported_even_while_locked(store: HistoryStore):
    """"3 de 10" convida; "trancada" não diz nada."""
    from app.history.achievements import calcular

    for indice in range(3):
        store.registrar(f"Filme {indice}", "MAX", 200, None, None, agora=indice)

    colecionador = next(c for c in calcular(store.listar()) if c.codigo == "COLECIONADOR")

    assert (colecionador.atual, colecionador.alvo) == (3, 10)
    assert colecionador.conquistada is False


def test_progress_never_goes_past_the_target(store: HistoryStore):
    """Doze de dez faria a barra estourar e a conta parecer errada."""
    from app.history.achievements import calcular

    for indice in range(14):
        store.registrar(f"Filme {indice}", "MAX", 200, None, None, agora=indice)

    colecionador = next(
        c for c in calcular(store.listar()) if c.codigo == "COLECIONADOR"
    ).como_dicionario()

    assert colecionador["atual"] == 10


def test_the_next_achievement_is_the_closest_one_not_the_next_in_the_list(store: HistoryStore):
    from app.history.achievements import calcular, nivel

    # Perto de "Turista" (2 serviços) e longe de "Cinquenta horas".
    store.registrar("Duna", "MAX", 600, None, None, agora=1)

    proxima = nivel(calcular(store.listar()))["proxima"]

    assert proxima["codigo"] == "TURISTA"


def test_the_profile_carries_the_achievements(cliente):
    cliente.dispatcher.history_recorder.store.registrar("Duna", "MAX", 600, None, None)

    resposta = cliente.get("/profile", headers=credenciais(cliente)).json()

    assert len(resposta["conquistas"]) >= 10
    assert resposta["progresso"]["nivel"] >= 1
    assert resposta["progresso"]["total"] == len(resposta["conquistas"])


def test_the_service_name_is_not_a_title(store: HistoryStore):
    """"Netflix" na tela é o catálogo aberto, não uma obra sendo assistida.

    Entrava no histórico como se fosse um título, contava para as conquistas e
    ainda ia parar na busca de capa.
    """
    gravador = HistoryRecorder(store)

    for _ in range(200):
        gravador.observar(tocando("Netflix", "NETFLIX"), 1.0)
    gravador.encerrar()

    assert store.listar() == []


def test_a_real_title_on_the_same_service_still_enters(store: HistoryStore):
    gravador = HistoryRecorder(store)

    for _ in range(200):
        gravador.observar(tocando("Round 6", "NETFLIX"), 1.0)
    gravador.encerrar()

    assert [item.titulo for item in store.listar()] == ["Round 6"]


# ── A mesma obra em duas linhas ───────────────────────────────────────────

def test_the_same_work_read_with_and_without_a_service_is_one_line(store: HistoryStore):
    """Medido no histórico real: A Casa do Dragão ocupava duas linhas —
    "MAX::a casa do dragao" e "-::a casa do dragao" — com o tempo dividido
    entre as duas e a mesma capa repetida nas duas. A pessoa viu uma série; a
    tela contava dois títulos.

    O serviço nem sempre é reconhecido na mesma leitura em que o título é:
    quando a API de mídia responde e a janela não, sobra o nome sem o serviço.
    """
    store.registrar("A Casa do Dragão", None, 360, 1135, 4928, agora=1)
    store.registrar("A Casa do Dragão", "MAX", 796, 2058, 4928, agora=2)

    linhas = store.listar()

    assert len(linhas) == 1
    assert linhas[0].segundos == 1156
    # E a linha que sobra é a que sabe o serviço, ou o Max deixaria de contar
    # como serviço usado.
    assert linhas[0].platform == "MAX"


def test_the_service_survives_a_reading_that_did_not_recognize_it(store: HistoryStore):
    """A ordem inversa: o serviço vem primeiro e a leitura seguinte não o
    reconhece. Sobrescrever com "desconhecido" apagaria o que já se sabia."""
    store.registrar("A Casa do Dragão", "MAX", 600, None, None, agora=1)
    store.registrar("A Casa do Dragão", None, 600, None, None, agora=2)

    linhas = store.listar()

    assert len(linhas) == 1
    assert linhas[0].platform == "MAX"
    assert linhas[0].segundos == 1200


def test_a_cover_found_on_one_line_survives_the_merge(store: HistoryStore):
    store.registrar(
        "A Casa do Dragão", None, 600, None, None,
        poster_url="https://image.tmdb.org/t/p/w342/dragao.jpg",
        generos=("Drama",), agora=1,
    )
    store.registrar("A Casa do Dragão", "MAX", 600, None, None, agora=2)

    linha = store.listar()[0]

    assert linha.poster_url.endswith("/dragao.jpg")
    assert linha.generos == ("Drama",)


def test_consolidating_merges_the_line_that_never_knew_the_service(store: HistoryStore):
    """A fusão vale para o que já está no arquivo. Uma correção que só valesse
    para o futuro deixaria a tela errada até alguém apagar o histórico."""
    # Escrito à força como duas linhas, do jeito que o arquivo antigo está.
    import json

    store._caminho.write_text(json.dumps({
        "-::a casa do dragao": {
            "titulo": "A Casa do Dragão", "platform": None, "segundos": 360.0,
            "posicao": 1135.0, "duracao": 4928.0, "vistoEm": 1.0,
            "posterUrl": None, "generos": [],
        },
        "MAX::a casa do dragao": {
            "titulo": "A Casa do Dragão", "platform": "MAX", "segundos": 796.0,
            "posicao": 2058.0, "duracao": 4928.0, "vistoEm": 2.0,
            "posterUrl": None, "generos": [],
        },
    }, ensure_ascii=False), encoding="utf-8")

    removidas = store.consolidar(lambda titulo: titulo)

    linhas = store.listar()
    assert removidas == 1
    assert len(linhas) == 1
    assert linhas[0].platform == "MAX"
    assert linhas[0].segundos == 1156


def test_the_same_name_on_two_known_services_stays_two_works(store: HistoryStore):
    """Só o serviço desconhecido é coringa. "O Justiceiro" é um filme de 2004
    no Max e uma série da Marvel no Disney+."""
    store.registrar("O Justiceiro", "MAX", 600, None, None, agora=1)
    store.registrar("O Justiceiro", "DISNEY_PLUS", 600, None, None, agora=2)

    assert len(store.listar()) == 2


# ── O que a janela sozinha não pode afirmar ───────────────────────────────

def test_a_window_only_reading_never_becomes_a_watched_title(store: HistoryStore):
    """Com a API de mídia pendurada, o que sobra é o título da janela — e numa
    série ele é o do EPISÓDIO. Medido: uma tarde de Rick and Morty virou quatro
    "títulos assistidos" com nome de episódio, um deles ("Campo dos Sonhos")
    com o pôster do filme de 1989 que se chama igual."""
    from app.media.now_playing import da_janela

    gravador = HistoryRecorder(store)
    episodio = da_janela("Campo dos Sonhos • HBO Max", "MAX")

    for _ in range(20):
        gravador.observar(episodio, SEGUNDOS_ENTRE_GRAVACOES)
    gravador.encerrar()

    assert store.listar() == []


def test_the_same_title_from_the_media_api_still_enters(store: HistoryStore):
    """A trava é sobre a origem da leitura, não sobre o nome: o que a API de
    mídia confirma continua contando normalmente."""
    gravador = HistoryRecorder(store)

    for _ in range(3):
        gravador.observar(tocando("Rick and Morty", platform="MAX"), SEGUNDOS_ENTRE_GRAVACOES)
    gravador.encerrar()

    assert [item.titulo for item in store.listar()] == ["Rick and Morty"]


def test_prime_video_counts_even_without_the_media_api(store: HistoryStore):
    """No Prime Video o título da janela é a OBRA, não o episódio — então uma
    leitura sem a API de mídia pode virar histórico. Medido: uma hora de Batman
    ficou sem contabilizar quando a regra tratava todos os serviços igual."""
    from app.media.now_playing import da_janela

    gravador = HistoryRecorder(store)
    batman = da_janela("Prime Video: Batman: Caped Crusader - Google Chrome", "PRIME_VIDEO")

    for _ in range(3):
        gravador.observar(batman, SEGUNDOS_ENTRE_GRAVACOES)
    gravador.encerrar()

    linhas = store.listar()
    assert [i.titulo for i in linhas] == ["Batman: Caped Crusader"]
    # E com o serviço, que é o que faltava no cartão e no "mais usado".
    assert linhas[0].platform == "PRIME_VIDEO"


def test_the_old_serviceless_batman_line_absorbs_the_new_one(store: HistoryStore):
    """O histórico real tem "-::batman: caped crusader", gravado quando o
    serviço não era reconhecido. A leitura nova traz o serviço, e as duas
    precisam virar uma linha só em vez de dois slots."""
    store.registrar("Batman: Caped Crusader", None, 3530, 484, 1680, agora=1)
    store.registrar("Batman: Caped Crusader", "PRIME_VIDEO", 600, 900, 1680, agora=2)

    linhas = store.listar()

    assert len(linhas) == 1
    assert linhas[0].platform == "PRIME_VIDEO"
    assert linhas[0].segundos == 4130
