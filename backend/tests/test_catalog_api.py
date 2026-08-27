import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import websocket as websocket_module
from app.catalog.store import TmdbKeyStore
from app.catalog.tmdb import TmdbCatalog
from app.main import app
from tests.test_catalog import HARRY_POTTER, PROVIDERS_BR, fake_client


AUTH = {"X-Device-Id": "device-catalogo", "X-Device-Token": "token-catalogo"}


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.delenv("CONTROLFAWKES_TMDB_KEY", raising=False)
    store = TmdbKeyStore(tmp_path / "tmdb.json")

    def montar(routes=None):
        catalogo = TmdbCatalog(
            client=fake_client({
                "/authentication": {"success": True, "status_code": 1},
                **(routes if routes is not None else {
                    # A busca de teste da chave é por "Interestelar" (ver
                    # `TmdbCatalog.verify`), e a fixture só servia Harry
                    # Potter. O caminho antigo aceitava qualquer resultado para
                    # qualquer consulta — a mesma frouxidão que fazia "O Rei"
                    # virar o homônimo de 2014. Agora o resultado precisa
                    # responder ao que foi buscado, então os dois estão aqui.
                    "/search/multi": {
                        "results": [
                            *HARRY_POTTER["results"],
                            {
                                "media_type": "movie", "id": 157336,
                                "title": "Interestelar",
                                "release_date": "2014-11-05", "popularity": 90.0,
                            },
                        ],
                    },
                    "/watch/providers": PROVIDERS_BR,
                }),
            }),
            key_store=store,
        )
        dispatcher = websocket_module.dispatcher
        dispatcher.catalog = catalogo
        dispatcher.device_store.add("device-catalogo", "Probe", "token-catalogo")
        return TestClient(app), catalogo

    yield montar
    websocket_module.dispatcher.device_store.revoke("device-catalogo")


def test_the_key_is_verified_against_the_real_api_before_being_saved(cliente):
    """Uma chave pode ter o formato certo e estar revogada. A única prova é
    uma busca de verdade."""
    client, catalogo = cliente()

    resposta = client.post("/catalog/tmdb", headers=AUTH, json={"apiKey": "chave-boa"})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["enabled"] is True
    assert corpo["source"] == "GUARDADA"
    # O veredito vem com o resultado real, não com um "ok" genérico.
    assert corpo["sample"]["title"]
    assert catalogo.enabled is True


def test_a_key_the_tmdb_refuses_is_rejected_and_not_saved(cliente):
    """O TMDB tem endpoint próprio para validar a chave; usá-lo é o que
    permite dizer "sua chave está errada" com certeza."""
    client, catalogo = cliente({
        "/authentication": {"success": False, "status_code": 7},
        "/search/multi": HARRY_POTTER,
        "/watch/providers": PROVIDERS_BR,
    })

    resposta = client.post("/catalog/tmdb", headers=AUTH, json={"apiKey": "chave-ruim"})

    assert resposta.status_code == 422
    assert "recusou esta chave" in resposta.json()["detail"]
    assert catalogo.enabled is False


def test_a_valid_key_with_an_empty_search_does_not_blame_the_key(cliente):
    """Chave boa e busca vazia é outro problema — provavelmente a região. Dizer
    "chave errada" mandaria a pessoa procurar no lugar errado."""
    client, catalogo = cliente({"/search/multi": {"results": []}})

    resposta = client.post("/catalog/tmdb", headers=AUTH, json={"apiKey": "chave-boa"})

    assert resposta.status_code == 422
    assert "chave é válida" in resposta.json()["detail"]
    assert catalogo.enabled is False


def test_a_network_failure_is_not_reported_as_an_invalid_key(cliente):
    """Dizer "chave inválida" quando o problema é a internet manda a pessoa
    procurar no lugar errado."""
    def explode(_request):
        raise httpx.ConnectError("sem rede")

    client, _ = cliente()
    websocket_module.dispatcher.catalog = TmdbCatalog(
        client=httpx.AsyncClient(transport=httpx.MockTransport(explode)),
        key_store=TmdbKeyStore(),
    )

    resposta = client.post("/catalog/tmdb", headers=AUTH, json={"apiKey": "qualquer"})

    assert resposta.status_code == 422 or resposta.status_code == 502


def test_the_environment_variable_wins_and_says_so(cliente, monkeypatch):
    """Aceitar a chave do celular e não usá-la seria mentir para quem colou."""
    monkeypatch.setenv("CONTROLFAWKES_TMDB_KEY", "chave-do-ambiente")
    client, _ = cliente()

    estado = client.get("/catalog/tmdb", headers=AUTH).json()
    resposta = client.post("/catalog/tmdb", headers=AUTH, json={"apiKey": "outra"})

    assert estado["envOverrides"] is True
    assert estado["source"] == "AMBIENTE"
    assert resposta.status_code == 409


def test_the_state_is_readable_before_configuring_anything(cliente):
    client, _ = cliente()

    estado = client.get("/catalog/tmdb", headers=AUTH).json()

    assert estado["enabled"] is False
    assert estado["source"] == "NENHUMA"
    assert estado["region"] == "BR"


def test_the_key_can_be_removed(cliente):
    client, catalogo = cliente()
    client.post("/catalog/tmdb", headers=AUTH, json={"apiKey": "chave-boa"})

    resposta = client.delete("/catalog/tmdb", headers=AUTH)

    assert resposta.status_code == 200
    assert resposta.json()["enabled"] is False
    assert catalogo.enabled is False


def test_configuring_the_catalog_needs_the_same_token_as_everything_else(cliente):
    client, _ = cliente()

    assert client.get("/catalog/tmdb").status_code == 401
    assert client.post("/catalog/tmdb", json={"apiKey": "x"}).status_code == 401
    assert client.delete("/catalog/tmdb").status_code == 401


def test_a_remote_origin_cannot_touch_the_catalog(cliente):
    client, _ = cliente()

    resposta = client.get(
        "/catalog/tmdb",
        headers={**AUTH, "Origin": "https://site-qualquer.com"},
    )

    assert resposta.status_code == 403
