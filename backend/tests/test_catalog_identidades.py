"""A associação `(provider, contentId) -> TMDB` — e o cuidado ao gravá-la.

`/watch/81043710` identifica a obra dentro da Netflix com certeza absoluta.
Não é um id do TMDB, e não vira um por decreto: alguém tem de descobrir a
ligação uma vez. O que este módulo garante é que, descoberta com segurança, ela
não se refaz pela busca por título — que é justamente a etapa frágil.

E a assimetria que importa: uma associação ERRADA gravada aqui é pior do que
nenhuma, porque vira identidade e passa a ganhar de todo o resto.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.catalog.identidades import MAXIMO, IdentidadeStore
from app.catalog.tmdb import TmdbCatalog


@pytest.fixture()
def store(tmp_path):
    return IdentidadeStore(tmp_path / "identidades.json")


def test_o_que_nunca_foi_associado_nao_inventa_id(store):
    assert store.tmdb_de("netflix", "81043710") is None


def test_o_que_foi_associado_volta(store):
    store.associar("netflix", "81043710", 504949, "MOVIE", "O Rei")

    assert store.tmdb_de("netflix", "81043710") == 504949


def test_o_provider_faz_parte_da_chave(store):
    """O mesmo número em serviços diferentes é outra obra. `81043710` na Netflix
    não tem nada a ver com `81043710` em lugar nenhum."""
    store.associar("netflix", "81043710", 504949, "MOVIE", "O Rei")

    assert store.tmdb_de("prime_video", "81043710") is None


def test_a_chave_ignora_caixa_e_espaco_do_provider(store):
    store.associar("Netflix", "81043710", 504949, "MOVIE", "O Rei")

    assert store.tmdb_de("netflix", " 81043710 ") == 504949


def test_associar_duas_vezes_o_mesmo_nao_muda_nada(store):
    store.associar("netflix", "1", 10, "MOVIE", "A")
    store.associar("netflix", "1", 10, "MOVIE", "A")

    assert json.loads(store._caminho.read_text(encoding="utf-8")).keys() == {"netflix::1"}


def test_uma_resolucao_melhor_informada_corrige_a_anterior(store):
    """Congelar o primeiro palpite seria congelar um erro. Quem grava só grava
    com resultado forte, então o mais recente é o mais informado."""
    store.associar("netflix", "1", 10, "MOVIE", "Palpite")
    store.associar("netflix", "1", 20, "TV", "Certo")

    assert store.tmdb_de("netflix", "1") == 20


def test_sem_provider_ou_sem_id_nao_grava_nem_le(store):
    assert store.associar(None, "1", 10, "MOVIE", "A") is False
    assert store.associar("netflix", None, 10, "MOVIE", "A") is False
    assert store.tmdb_de(None, "1") is None
    assert store.tmdb_de("netflix", None) is None


def test_arquivo_corrompido_nao_derruba_o_enriquecimento(store):
    """Enriquecer é acessório. Um arquivo estragado faz voltar à busca por
    título, nunca faz o histórico parar."""
    store._caminho.write_text("{isto não é json", encoding="utf-8")

    assert store.tmdb_de("netflix", "1") is None
    assert store.associar("netflix", "1", 10, "MOVIE", "A") is True
    assert store.tmdb_de("netflix", "1") == 10


def test_o_arquivo_nao_cresce_sem_limite(store):
    for i in range(MAXIMO + 20):
        store.associar("netflix", str(i), i, "MOVIE", f"Obra {i}")

    dados = json.loads(store._caminho.read_text(encoding="utf-8"))
    assert len(dados) == MAXIMO
    # As mais antigas saem; a última entrada continua lá.
    assert store.tmdb_de("netflix", str(MAXIMO + 19)) == MAXIMO + 19


def test_esquecer_apaga_uma_associacao_errada(store):
    store.associar("netflix", "1", 10, "MOVIE", "A")

    assert store.esquecer("netflix", "1") is True
    assert store.tmdb_de("netflix", "1") is None
    assert store.esquecer("netflix", "1") is False


# ── A ligação com a resolução ─────────────────────────────────────────────


O_REI = {
    "media_type": "movie", "id": 504949, "title": "O Rei",
    "original_title": "The King", "release_date": "2019-10-11",
    "poster_path": "/rei.jpg", "genre_ids": [], "popularity": 6.63,
}
HOMONIMO = {
    "media_type": "movie", "id": 999001, "title": "O Rei",
    "release_date": "2014-01-01", "poster_path": "/outro.jpg",
    "genre_ids": [], "popularity": 6.40,
}


def _catalogo(store, resultados):
    def handler(request: httpx.Request) -> httpx.Response:
        if "/search/" in request.url.path:
            tipo = "movie" if request.url.path.endswith("/search/movie") else "tv"
            uteis = [r for r in resultados if r.get("media_type") == tipo]
            pagina = request.url.params.get("page", "1")
            return httpx.Response(200, json={"results": uteis if pagina == "1" else []})
        return httpx.Response(200, json={"genres": [], "results": {}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return TmdbCatalog(api_key="chave", client=client, identidades=store)


@pytest.mark.asyncio
async def test_uma_resolucao_forte_deixa_a_associacao_guardada(store):
    """Resolvido com ano e tipo: isso é decidir por algo ALÉM do nome."""
    tmdb = _catalogo(store, [O_REI, HOMONIMO])

    await tmdb.detalhes_de(
        "O Rei", ano=2019, tipo="MOVIE",
        provider="netflix", provider_content_id="81043710",
    )

    assert store.tmdb_de("netflix", "81043710") == 504949


@pytest.mark.asyncio
async def test_uma_escolha_so_por_nome_nao_vira_identidade(store):
    """Dois "O Rei" com popularidade próxima e nenhum ano: a resolução ou fica
    ambígua ou vence só por fama. Nenhum dos dois é seguro o bastante para
    virar identidade permanente."""
    tmdb = _catalogo(store, [O_REI, HOMONIMO])

    await tmdb.detalhes_de(
        "O Rei", provider="netflix", provider_content_id="81043710",
    )

    assert store.tmdb_de("netflix", "81043710") is None


@pytest.mark.asyncio
async def test_a_associacao_guardada_decide_sem_precisar_do_ano(store):
    """O ganho concreto: da segunda vez em diante, o mesmo par não depende mais
    de ano, tipo nem desempate por fama. A busca frágil por título não decide
    mais nada."""
    store.associar("netflix", "81043710", 504949, "MOVIE", "O Rei")
    tmdb = _catalogo(store, [HOMONIMO, O_REI])

    poster, _ = await tmdb.detalhes_de(
        "O Rei", provider="netflix", provider_content_id="81043710",
    )

    assert poster is not None
    assert poster.endswith("/rei.jpg")


@pytest.mark.asyncio
async def test_sem_id_do_provider_nada_e_guardado(store, tmp_path):
    """Hoje quase toda mídia chega só com o nome da janela. Isso não pode criar
    lixo no arquivo."""
    tmdb = _catalogo(store, [O_REI])

    await tmdb.detalhes_de("O Rei", ano=2019, tipo="MOVIE")

    assert not (tmp_path / "identidades.json").exists()
