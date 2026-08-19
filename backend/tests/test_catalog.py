import httpx
import pytest

from app.catalog.tmdb import TmdbCatalog, platform_for_provider


HARRY_POTTER = {
    "results": [
        # O /search/multi devolve pessoas junto, e o ator costuma vir antes.
        {"media_type": "person", "id": 10980, "name": "Daniel Radcliffe", "popularity": 90.0},
        {
            "media_type": "movie",
            "id": 671,
            "title": "Harry Potter e a Pedra Filosofal",
            "release_date": "2001-11-16",
            "poster_path": "/abc.jpg",
            "popularity": 120.5,
        },
        {
            "media_type": "movie",
            "id": 672,
            "title": "Harry Potter e a Câmara Secreta",
            "release_date": "2002-11-13",
            "popularity": 80.0,
        },
    ],
}

PROVIDERS_BR = {
    "results": {
        "BR": {
            "flatrate": [
                {"provider_id": 1899, "provider_name": "Max"},
                {"provider_id": 619, "provider_name": "Algum Serviço Desconhecido"},
            ],
            "rent": [{"provider_id": 2, "provider_name": "Apple TV"}],
        },
        "US": {"flatrate": [{"provider_id": 8, "provider_name": "Netflix"}]},
    },
}


def fake_client(routes: dict[str, dict], registro: list[str] | None = None):
    """Cliente falso do TMDB.

    Um stub de `/search/multi` também responde `/search/movie` e `/search/tv`,
    filtrado por tipo — que é como a API de verdade se comporta. Isso existe
    porque o resolver deixou de usar `/search/multi`: ele não trazia
    "O Rei"/"The King" (2019) nem na página 3 de 57, medido contra a API. Sem
    esta ponte, cada fixture teria de ser reescrita em três, e o que os testes
    verificam não mudou.
    """
    def por_tipo(payload: dict, media_type: str) -> dict:
        resultados = payload.get("results")
        if not isinstance(resultados, list):
            return payload
        return {
            **payload,
            "results": [
                item for item in resultados
                if isinstance(item, dict)
                and item.get("media_type", media_type) == media_type
            ],
        }

    def handler(request: httpx.Request) -> httpx.Response:
        caminho = request.url.path
        if registro is not None:
            registro.append(caminho)
        for path, payload in routes.items():
            if caminho.endswith(path):
                return httpx.Response(200, json=payload)
            if path.endswith("/search/multi"):
                if caminho.endswith("/search/movie"):
                    return httpx.Response(200, json=por_tipo(payload, "movie"))
                if caminho.endswith("/search/tv"):
                    return httpx.Response(200, json=por_tipo(payload, "tv"))
        return httpx.Response(404, json={})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def catalog(routes, **kwargs) -> TmdbCatalog:
    return TmdbCatalog(api_key="chave-de-teste", client=fake_client(routes), **kwargs)


@pytest.mark.asyncio
async def test_finds_where_the_title_is_available():
    found = await catalog({
        "/search/multi": HARRY_POTTER,
        "/watch/providers": PROVIDERS_BR,
    }).lookup("harry potter")

    assert found is not None
    assert found.title == "Harry Potter e a Pedra Filosofal"
    assert found.year == 2001
    assert found.platforms == ["MAX"]
    assert found.poster_url.endswith("/abc.jpg")


@pytest.mark.asyncio
async def test_a_person_never_wins_over_the_title():
    """O ator vem antes do filme quando o nome bate; escolher a pessoa faria a
    busca perguntar por providers de um ser humano."""
    found = await catalog({
        "/search/multi": HARRY_POTTER,
        "/watch/providers": PROVIDERS_BR,
    }).lookup("harry potter")

    assert found.title.startswith("Harry Potter e a Pedra")


@pytest.mark.asyncio
async def test_only_the_configured_region_counts():
    """A Netflix aparece só no catálogo dos EUA: oferecê-la aqui mandaria a
    pessoa a uma busca que não tem o título."""
    found = await catalog({
        "/search/multi": HARRY_POTTER,
        "/watch/providers": PROVIDERS_BR,
    }).lookup("harry potter")

    assert "NETFLIX" not in found.platforms


@pytest.mark.asyncio
async def test_rent_and_buy_are_left_out():
    """Quem pediu para assistir não pediu uma tela de compra."""
    found = await catalog({
        "/search/multi": HARRY_POTTER,
        "/watch/providers": PROVIDERS_BR,
    }).lookup("harry potter")

    assert found.platforms == ["MAX"]


@pytest.mark.asyncio
async def test_an_unknown_provider_is_ignored_instead_of_breaking():
    found = await catalog({
        "/search/multi": HARRY_POTTER,
        "/watch/providers": {
            "results": {"BR": {"flatrate": [{"provider_name": "Serviço Novo"}]}},
        },
    }).lookup("harry potter")

    assert found is not None
    assert found.platforms == []


@pytest.mark.asyncio
async def test_the_title_still_comes_back_when_nobody_streams_it():
    """Saber que o título existe e não está em lugar nenhum é informação útil;
    devolver None faria a interface fingir que a busca falhou."""
    found = await catalog({
        "/search/multi": HARRY_POTTER,
        "/watch/providers": {"results": {}},
    }).lookup("harry potter")

    assert found is not None
    assert found.platforms == []


@pytest.mark.asyncio
async def test_series_are_looked_up_on_the_tv_endpoint():
    caminhos: list[str] = []
    tmdb = TmdbCatalog(
        api_key="chave",
        client=fake_client(
            {
                "/search/multi": {
                    "results": [{
                        "media_type": "tv",
                        "id": 1399,
                        "name": "A Casa do Dragão",
                        "first_air_date": "2022-08-21",
                        "popularity": 50.0,
                    }],
                },
                "/watch/providers": PROVIDERS_BR,
            },
            caminhos,
        ),
    )

    found = await tmdb.lookup("casa do dragao")

    assert found.year == 2022
    assert any("/tv/1399/watch/providers" in caminho for caminho in caminhos)


@pytest.mark.asyncio
async def test_no_key_means_no_call_at_all():
    tmdb = TmdbCatalog(api_key="", client=fake_client({}))

    assert tmdb.enabled is False
    assert await tmdb.lookup("harry potter") is None


@pytest.mark.asyncio
async def test_a_network_failure_falls_back_to_the_manual_choice():
    """O catálogo é atalho. Indisponível, a escolha manual continua igual."""

    def explode(_request):
        raise httpx.ConnectError("sem rede")

    tmdb = TmdbCatalog(
        api_key="chave",
        client=httpx.AsyncClient(transport=httpx.MockTransport(explode)),
    )

    assert await tmdb.lookup("harry potter") is None


@pytest.mark.asyncio
async def test_an_unexpected_payload_never_raises():
    tmdb = catalog({"/search/multi": {"results": "isto não é uma lista"}})

    assert await tmdb.lookup("harry potter") is None


@pytest.mark.asyncio
async def test_an_empty_query_is_not_sent_to_the_network():
    caminhos: list[str] = []
    tmdb = TmdbCatalog(api_key="chave", client=fake_client({}, caminhos))

    assert await tmdb.lookup("   ") is None
    assert caminhos == []


@pytest.mark.parametrize(
    ("nome", "esperado"),
    [
        ("Netflix", "NETFLIX"),
        ("Amazon Prime Video", "PRIME_VIDEO"),
        ("Prime Video", "PRIME_VIDEO"),
        ("Disney Plus", "DISNEY_PLUS"),
        ("Disney+", "DISNEY_PLUS"),
        ("Max", "MAX"),
        ("HBO Max", "MAX"),
        ("YouTube Premium", "YOUTUBE"),
        ("Paramount+", None),
    ],
)
def test_provider_names_map_to_the_platforms_the_control_knows(nome, esperado):
    """O casamento é por nome, não por id: os ids mudam por região, e o do Max
    já mudou quando a HBO renomeou o serviço."""
    assert platform_for_provider(nome) == esperado


COLECAO_BUSCA = {"results": [{"id": 1241, "name": "Harry Potter: Coleção"}]}
COLECAO_DETALHE = {
    "parts": [
        # Fora de ordem de propósito: a ordem que importa é a de estreia.
        {"id": 674, "title": "Cálice de Fogo", "release_date": "2005-11-16"},
        {"id": 671, "title": "Pedra Filosofal", "release_date": "2001-11-16"},
        {"id": 675, "title": "Ordem da Fênix", "release_date": "2007-06-28"},
        {"id": 672, "title": "Câmara Secreta", "release_date": "2002-11-13"},
        {"id": 673, "title": "Prisioneiro de Azkaban", "release_date": "2004-05-31"},
    ],
}


@pytest.mark.asyncio
async def test_a_number_at_the_end_picks_the_nth_film_of_the_franchise():
    """Ninguém decora "Harry Potter e a Ordem da Fênix"; todo mundo sabe que é
    o quinto. Medido contra a API real: "harry potter 5" não devolvia nada."""
    found = await catalog({
        "/search/multi": {"results": []},
        "/search/collection": COLECAO_BUSCA,
        "/collection/1241": COLECAO_DETALHE,
        "/watch/providers": PROVIDERS_BR,
    }).lookup("harry potter 5")

    assert found is not None
    assert found.title == "Ordem da Fênix"
    assert found.platforms == ["MAX"]


@pytest.mark.asyncio
async def test_the_normal_search_always_wins_first():
    """Medido: "Blade Runner 2049" e "velozes e furiosos 7" já são achados pela
    busca normal, porque o número faz parte do nome. Tentar a coleção antes
    estragaria os dois.

    A fixture devolvia "Harry Potter" para esta consulta, e o caminho antigo
    aceitava — era a mesma frouxidão que fazia "O Rei" virar o homônimo de
    2014. Agora o resultado precisa responder ao que foi buscado, então a
    fixture passou a devolver o filme que a busca de verdade devolveria.
    """
    caminhos: list[str] = []
    blade_runner = {"results": [{
        "media_type": "movie", "id": 335984, "title": "Blade Runner 2049",
        "release_date": "2017-10-04", "popularity": 60.0,
    }]}
    tmdb = TmdbCatalog(
        api_key="chave",
        client=fake_client(
            {"/search/multi": blade_runner, "/watch/providers": PROVIDERS_BR},
            caminhos,
        ),
    )

    found = await tmdb.lookup("Blade Runner 2049")

    assert found is not None
    assert not any("/search/collection" in caminho for caminho in caminhos)


@pytest.mark.asyncio
async def test_an_absurd_position_is_not_invented():
    found = await catalog({
        "/search/multi": {"results": []},
        "/search/collection": COLECAO_BUSCA,
        "/collection/1241": COLECAO_DETALHE,
    }).lookup("harry potter 12")

    assert found is None


@pytest.mark.asyncio
async def test_a_number_that_is_probably_a_year_is_left_alone():
    """Acima de vinte é quase certamente ano ou parte do nome."""
    caminhos: list[str] = []
    tmdb = TmdbCatalog(
        api_key="chave",
        client=fake_client({"/search/multi": {"results": []}}, caminhos),
    )

    assert await tmdb.lookup("alguma coisa 1999") is None
    assert not any("/search/collection" in caminho for caminho in caminhos)


PROVEDORES_BR = {
    "results": [
        {"provider_id": 8, "provider_name": "Netflix"},
        {"provider_id": 1899, "provider_name": "HBO Max"},
        {"provider_id": 337, "provider_name": "Disney Plus"},
        {"provider_id": 619, "provider_name": "Serviço Que Não Conhecemos"},
    ],
}

DESCOBERTA = {
    "results": [
        {"title": "Com capa", "release_date": "2024-01-01", "poster_path": "/a.jpg"},
        {"title": "Sem capa", "release_date": "2023-01-01"},
        {"title": "Outra com capa", "release_date": "2022-01-01", "poster_path": "/b.jpg"},
    ],
}


@pytest.mark.asyncio
async def test_provider_ids_come_from_the_name_not_from_a_hardcoded_number():
    """Os ids mudam por região, e o do Max já mudou quando a HBO renomeou o
    serviço. Fixá-los no código seria uma quebra esperando a data."""
    ids = await catalog({"/watch/providers/movie": PROVEDORES_BR}).provider_ids()

    assert ids == {"NETFLIX": 8, "MAX": 1899, "DISNEY_PLUS": 337}


@pytest.mark.asyncio
async def test_highlights_skip_titles_without_a_poster():
    """A tela é feita de capas: um título sem capa vira um retângulo vazio."""
    achados = await catalog({
        "/watch/providers/movie": PROVEDORES_BR,
        "/discover/movie": DESCOBERTA,
    }).highlights("NETFLIX")

    assert [d.title for d in achados] == ["Com capa", "Outra com capa"]
    assert all(d.poster_url for d in achados)


@pytest.mark.asyncio
async def test_a_service_we_do_not_know_never_becomes_a_row():
    ids = await catalog({"/watch/providers/movie": PROVEDORES_BR}).provider_ids()

    assert 619 not in ids.values()


@pytest.mark.asyncio
async def test_highlights_are_empty_without_a_key():
    tmdb = TmdbCatalog(api_key="", client=fake_client({}))

    assert await tmdb.highlights("NETFLIX") == []


@pytest.mark.asyncio
async def test_the_provider_list_is_resolved_only_once():
    caminhos: list[str] = []
    tmdb = TmdbCatalog(
        api_key="chave",
        client=fake_client(
            {"/watch/providers/movie": PROVEDORES_BR, "/discover/movie": DESCOBERTA},
            caminhos,
        ),
    )

    await tmdb.highlights("NETFLIX")
    await tmdb.highlights("MAX")

    assert sum("/watch/providers/movie" in c for c in caminhos) == 1


# --- Filme ou série: o mesmo nome, duas obras diferentes -----------------

# Medido na API real: "o justiceiro" devolve o filme de 2004, que está no Max,
# e a série da Marvel de 2017, que está no Disney+. Foi o caso que o usuário
# encontrou assistindo à série e recebendo o filme.
JUSTICEIRO = {
    "results": [
        {
            "media_type": "movie",
            "id": 9271,
            "title": "O Justiceiro",
            "release_date": "2004-04-16",
            "popularity": 40.0,
        },
        {
            "media_type": "tv",
            "id": 67178,
            "name": "Marvel - O Justiceiro",
            "first_air_date": "2017-11-17",
            "popularity": 30.0,
        },
    ],
}

SO_NO_MAX = {"results": {"BR": {"flatrate": [{"provider_id": 1899, "provider_name": "Max"}]}}}
SO_NO_DISNEY = {
    "results": {"BR": {"flatrate": [{"provider_id": 337, "provider_name": "Disney Plus"}]}}
}


@pytest.mark.asyncio
async def test_the_movie_and_the_series_both_come_back_when_both_answer():
    tmdb = catalog({
        "/search/multi": JUSTICEIRO,
        "/movie/9271/watch/providers": SO_NO_MAX,
        "/tv/67178/watch/providers": SO_NO_DISNEY,
    })

    opcoes = await tmdb.lookup_options("o justiceiro")

    assert [(o.kind, o.platforms) for o in opcoes] == [
        ("MOVIE", ["MAX"]),
        ("TV", ["DISNEY_PLUS"]),
    ]


@pytest.mark.asyncio
async def test_the_other_kind_is_dropped_when_it_does_not_answer_the_query():
    """Um título do outro tipo que não responde à consulta é ruído, não escolha.

    Medido: "the boys" traz o filme "Os Garotos Perdidos" junto com a série.
    Oferecer os dois faria a tela perguntar algo que não tem resposta certa.
    """
    tmdb = catalog({
        "/search/multi": {
            "results": [
                {
                    "media_type": "tv",
                    "id": 76479,
                    "name": "The Boys",
                    "first_air_date": "2019-07-25",
                    "popularity": 200.0,
                },
                {
                    "media_type": "movie",
                    "id": 726,
                    "title": "Os Garotos Perdidos",
                    "release_date": "1987-07-31",
                    "popularity": 300.0,
                },
            ],
        },
        "/watch/providers": PROVIDERS_BR,
    })

    opcoes = await tmdb.lookup_options("the boys")

    assert [o.kind for o in opcoes] == ["TV"]


@pytest.mark.asyncio
async def test_the_best_match_comes_first_even_when_the_other_is_more_popular():
    tmdb = catalog({
        "/search/multi": {
            "results": [
                {
                    "media_type": "movie",
                    "id": 1,
                    "title": "Interestelar: O Documentário",
                    "release_date": "2015-01-01",
                    "popularity": 900.0,
                },
                {
                    "media_type": "tv",
                    "id": 2,
                    "name": "Interestelar",
                    "first_air_date": "2020-01-01",
                    "popularity": 5.0,
                },
            ],
        },
        "/watch/providers": PROVIDERS_BR,
    })

    opcoes = await tmdb.lookup_options("interestelar")

    assert [o.title for o in opcoes] == ["Interestelar", "Interestelar: O Documentário"]


@pytest.mark.asyncio
async def test_lookup_still_returns_a_single_title():
    """`lookup` é o caminho antigo e não pode ter mudado de forma."""
    tmdb = catalog({"/search/multi": JUSTICEIRO, "/watch/providers": SO_NO_MAX})

    found = await tmdb.lookup("o justiceiro")

    assert found.title == "O Justiceiro"


# --- Quando a busca literal do TMDB volta vazia -------------------------

def busca_exigente(esperado: str, resultado: dict):
    """Um TMDB que só responde à grafia exata — que é como ele se comporta."""
    tentativas: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(("/search/multi", "/search/movie", "/search/tv")):
            consulta = request.url.params.get("query", "")
            # Uma CONSULTA pode bater em dois endpoints (`/search/movie` e
            # `/search/tv`) e em mais de uma página. O que estes testes medem é
            # a sequência de tentativas de RECUO — quantas grafias diferentes
            # foram pedidas —, não quantas requisições saíram.
            if not tentativas or tentativas[-1] != consulta:
                tentativas.append(consulta)
            achou = consulta == esperado
            # O endpoint de filme não devolve série e vice-versa. Sem isto a
            # mesma obra aparecia duas vezes, como MOVIE e como TV, e virava um
            # empate fantasma que não existe na API real.
            tipo = "movie" if request.url.path.endswith("/search/movie") else "tv"
            combina = resultado.get("media_type", tipo) == tipo
            return httpx.Response(
                200, json={"results": [resultado] if achou and combina else []},
            )
        return httpx.Response(200, json=PROVIDERS_BR)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), tentativas


BATMAN = {
    "media_type": "tv",
    "id": 1,
    "name": "Batman: Cruzado Encapuzado",
    "first_air_date": "2024-08-01",
    "poster_path": "/batman.jpg",
    "genre_ids": [16],
    "popularity": 50.0,
}


@pytest.mark.asyncio
async def test_an_extra_connecting_word_no_longer_loses_the_title():
    """Medido na API real: o catálogo tem "Batman: Cruzado Encapuzado", e a
    busca por "Batman: Cruzado e Encapuzado" — que é como o serviço mostra —
    voltava vazia. Uma palavra a mais e a resposta era nada."""
    client, tentativas = busca_exigente("Batman: Cruzado Encapuzado", BATMAN)
    tmdb = TmdbCatalog(api_key="chave", client=client)

    poster, _ = await tmdb.detalhes_de("Batman: Cruzado e Encapuzado")

    assert poster is not None
    assert tentativas == ["Batman: Cruzado e Encapuzado", "Batman: Cruzado Encapuzado"]


@pytest.mark.asyncio
async def test_the_beginning_of_the_name_is_the_last_resort():
    client, tentativas = busca_exigente("Batman Cruzado", BATMAN)
    tmdb = TmdbCatalog(api_key="chave", client=client)

    poster, _ = await tmdb.detalhes_de("Batman: O Cruzado Encapuzado Ressurge")

    assert poster is not None
    # Três tentativas no máximo, e cada uma mais curta que a anterior.
    assert len(tentativas) == 3
    assert tentativas[-1] == "Batman Cruzado"


@pytest.mark.asyncio
async def test_a_title_found_at_once_costs_a_single_request():
    """O caminho normal não pode ficar mais caro por causa do recuo."""
    client, tentativas = busca_exigente("Batman: Cruzado Encapuzado", BATMAN)
    tmdb = TmdbCatalog(api_key="chave", client=client)

    await tmdb.detalhes_de("Batman: Cruzado Encapuzado")

    assert tentativas == ["Batman: Cruzado Encapuzado"]


@pytest.mark.asyncio
async def test_a_name_that_exists_nowhere_gives_up_instead_of_inventing():
    client, tentativas = busca_exigente("nada disso existe", BATMAN)
    tmdb = TmdbCatalog(api_key="chave", client=client)

    poster, generos = await tmdb.detalhes_de("Filme Que Não Existe Mesmo")

    assert (poster, generos) == (None, ())
    assert len(tentativas) <= 3


@pytest.mark.asyncio
async def test_the_service_name_never_decides_which_cover_to_use():
    """Aconteceu na tela: o histórico guardou "Prime Video: Batman: Caped
    Crusader" e a capa que apareceu foi a de um evento de boxe japonês —
    "Prime Video Boxing 11" —, porque as duas dividem o nome do serviço."""
    boxe = {
        "media_type": "tv", "id": 9, "name": "Prime Video Boxing 11",
        "poster_path": "/boxe.jpg", "genre_ids": [], "popularity": 90.0,
    }
    tmdb = catalog({"/search/multi": {"results": [boxe]}, "/watch/providers": PROVIDERS_BR})

    poster, _ = await tmdb.detalhes_de("Prime Video: Batman: Caped Crusader")

    assert poster is None


@pytest.mark.asyncio
async def test_a_translated_title_still_counts_as_the_same_thing():
    """"Caped Crusader" virou "Cruzado Encapuzado" — só "Batman" sobreviveu."""
    traduzido = {
        "media_type": "tv", "id": 1, "name": "Batman: Cruzado Encapuzado",
        "poster_path": "/batman.jpg", "genre_ids": [16], "popularity": 50.0,
    }
    tmdb = catalog({
        "/search/multi": {"results": [traduzido]},
        "/genre/movie/list": {"genres": [{"id": 16, "name": "Animação"}]},
        "/genre/tv/list": {"genres": []},
        "/watch/providers": PROVIDERS_BR,
    })

    poster, generos = await tmdb.detalhes_de("Batman: Caped Crusader")

    assert poster is not None
    assert generos == ("Animação",)


@pytest.mark.asyncio
async def test_a_short_name_is_not_blocked_by_the_shared_word_rule():
    """"Duna" não tem palavra longa de sobra para comparar; barrar seria pior."""
    duna = {
        "media_type": "movie", "id": 2, "title": "Duna: Parte Dois",
        "poster_path": "/duna.jpg", "genre_ids": [], "popularity": 80.0,
    }
    tmdb = catalog({"/search/multi": {"results": [duna]}, "/watch/providers": PROVIDERS_BR})

    poster, _ = await tmdb.detalhes_de("Duna")

    assert poster is not None


def test_one_letter_no_longer_erases_the_right_title():
    """Medido na tela: "The gentleman" devolvia um homônimo de 2000 porque o
    filme do Guy Ritchie se chama "The Gentlemen", com "e" — e o texto contido
    exigia a grafia exata."""
    assert TmdbCatalog.quanto_casa("The Gentlemen", "The gentleman") > 0
    # O exato continua ganhando de quem só é parecido.
    assert (
        TmdbCatalog.quanto_casa("The Gentleman", "The gentleman")
        > TmdbCatalog.quanto_casa("The Gentlemen", "The gentleman")
    )


def test_being_tolerant_is_not_being_indiscriminate():
    """Tolerar uma letra não pode virar tolerar qualquer coisa."""
    assert TmdbCatalog.quanto_casa("Interestelar", "Duna") == 0
    assert TmdbCatalog.quanto_casa("Prime Video Boxing 11", "Batman") == 0


# O nome brasileiro e o original quase nunca são o mesmo, e quem digita usa o
# que viu na tela do serviço. Medido contra a API: a busca por "the gentlemen"
# traz o filme do Guy Ritchie em PRIMEIRO lugar, mas com `title` "Magnatas do
# Crime" — e comparar só com esse nome dava zero, o que fazia a regra de
# descarte jogar fora justamente o resultado certo.
GENTLEMEN = {
    "results": [{
        "media_type": "movie", "id": 1,
        "title": "Magnatas do Crime", "original_title": "The Gentlemen",
        "release_date": "2020-01-01", "poster_path": "/gentlemen.jpg",
        "genre_ids": [], "popularity": 90.0,
    }],
}


@pytest.mark.asyncio
async def test_the_brazilian_name_does_not_hide_the_original():
    found = await catalog({
        "/search/multi": GENTLEMEN,
        "/watch/providers": PROVIDERS_BR,
    }).lookup("the gentlemen")

    assert found is not None
    assert found.year == 2020


@pytest.mark.asyncio
async def test_the_cover_comes_from_the_right_work():
    """Medido: a capa vinha de "The League of Gentlemen", uma série de 1999 que
    não tem nada a ver — o filme certo era recusado por se chamar "Magnatas do
    Crime" na resposta em pt-BR."""
    liga = {
        "media_type": "tv", "id": 2,
        "title": "The League of Gentlemen", "original_name": "The League of Gentlemen",
        "poster_path": "/liga.jpg", "genre_ids": [], "popularity": 5.0,
    }
    tmdb = catalog({
        "/search/multi": {"results": [GENTLEMEN["results"][0], liga]},
        "/watch/providers": PROVIDERS_BR,
    })

    poster, _ = await tmdb.detalhes_de("The Gentlemen")

    assert poster is not None and poster.endswith("/gentlemen.jpg")


def test_matching_uses_the_best_of_the_names():
    tmdb = TmdbCatalog(api_key="chave-de-teste")
    item = GENTLEMEN["results"][0]

    assert tmdb._casa_com(item, "the gentlemen") == 3
    # E o nome traduzido continua valendo para quem procura por ele.
    assert tmdb._casa_com(item, "magnatas do crime") == 3
    # Sem virar indiscriminado: outro título não passa a casar.
    assert tmdb._casa_com(item, "interestelar") == 0


# ── A busca usa o mesmo motor da identificação ────────────────────────────
#
# A busca ficou de fora quando o resolver entrou, e continuou com o defeito que
# ele existe para corrigir. Medido contra a API real em 19/08/2026, ANTES:
#
#   "O Rei"           devolvia o homônimo de 2014
#   "The king"        devolvia "The King" (2017) e "O Rei do Bairro" (1998)
#   "Capitão América" devolvia o filme de 1991
#   "Flash"           devolvia "Flash" (2018)
#
# Nenhum é falta de ranking: o candidato certo não estava na lista, porque
# `/search/multi` numa página só não o traz.


O_REI_DUPLO = {"results": [
    {"media_type": "movie", "id": 999001, "title": "O Rei",
     "release_date": "2014-01-01", "popularity": 2.01},
    {"media_type": "movie", "id": 504949, "title": "O Rei",
     "original_title": "The King", "release_date": "2019-10-11",
     "popularity": 6.63},
    {"media_type": "movie", "id": 8587, "title": "O Rei Leão",
     "release_date": "1994-06-24", "popularity": 32.61},
]}


@pytest.mark.asyncio
async def test_a_busca_nao_devolve_mais_o_homonimo_menos_relevante():
    """O caso que o usuário relatou. "O Rei Leão" é cinco vezes mais popular e
    continua perdendo, porque casamento exato de título é um NÍVEL acima."""
    opcoes = await catalog({
        "/search/multi": O_REI_DUPLO, "/watch/providers": PROVIDERS_BR,
    }).lookup_options("O Rei")

    assert opcoes[0].title == "O Rei"
    assert opcoes[0].year == 2019


@pytest.mark.asyncio
async def test_o_titulo_original_encontra_a_obra_pelo_nome_traduzido():
    """"The king" digitado, "O Rei" no catálogo. O TMDB devolve os dois nomes e
    o casamento acontece sem tradução manual em lugar nenhum."""
    opcoes = await catalog({
        "/search/multi": O_REI_DUPLO, "/watch/providers": PROVIDERS_BR,
    }).lookup_options("The king")

    assert (opcoes[0].title, opcoes[0].year) == ("O Rei", 2019)


@pytest.mark.asyncio
async def test_a_segunda_vaga_e_do_mais_famoso_e_nao_do_segundo_melhor():
    """As duas vagas respondem perguntas diferentes de propósito.

    Medido: "Capitão América" casa EXATO com o filme de 1990, que por nível
    ganha do "Capitão América" da Marvel — e o de 1990 é uma resposta legítima,
    é literalmente o nome. Mas quase ninguém quer ele.

    Deixar a fama mandar na primeira vaga estragaria o caso oposto: "O Rei"
    devolveria "O Rei Leão". Então a fama não decide quem vence — decide o que
    aparece ao lado.
    """
    opcoes = await catalog({
        "/search/multi": O_REI_DUPLO, "/watch/providers": PROVIDERS_BR,
    }).lookup_options("O Rei")

    # Duas opções, e "O Rei Leão" não é nenhuma delas — apesar de ser cinco
    # vezes mais popular. "rei" tem três letras e não conta como começo que
    # identifique: é a mesma trava que impede "Prime Video" de ligar um filme a
    # um evento de boxe.
    assert [(o.title, o.year) for o in opcoes] == [("O Rei", 2019), ("O Rei", 2014)]


@pytest.mark.asyncio
async def test_uma_busca_sem_resposta_nao_devolve_um_titulo_qualquer():
    """A frouxidão que sustentava o bug: qualquer resultado servia para
    qualquer consulta."""
    opcoes = await catalog({
        "/search/multi": O_REI_DUPLO, "/watch/providers": PROVIDERS_BR,
    }).lookup_options("Um Filme Que Não Existe Mesmo")

    assert opcoes == []
