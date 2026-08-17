"""A rota interna de ingestão — as trancas, e a validação que sobrevive a elas.

`/bridge/eventos` é a única rota do ControlFawkes que não existe para o celular.
Ela existe para o Native Host, na mesma máquina, e por isso é mais fechada do
que todas as outras.

O que se prova aqui, em duas metades:

    autenticação  quem mandou? (loopback, ausência de `Origin`, credencial)
    validação     isto é utilizável? (Fase 6, INTEIRA, depois de autenticar)

Um host autenticado que mande `currentTime` além do fim do vídeo continua sendo
recusado. Autenticar não é confiar.
"""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import bridge
from app.bridge.credencial import CABECALHO, CredencialDaPonte


@pytest.fixture()
def segredo(tmp_path, monkeypatch):
    credencial = CredencialDaPonte(tmp_path / "credencial")
    monkeypatch.setattr(bridge, "credencial", credencial)
    return credencial.garantir()


def _servidor(endereco: str) -> TestClient:
    """Um cliente que diz de ONDE o pedido vem.

    Por padrão o `TestClient` se apresenta como `testclient`, que não é
    endereço nenhum — e um endereço que não é loopback é recusado, como tem de
    ser. Dizer o endereço aqui é o que torna a tranca testável nos dois
    sentidos em vez de só no de fora.
    """
    app = FastAPI()
    app.include_router(bridge.router)
    return TestClient(app, client=(endereco, 51234))


@pytest.fixture()
def client():
    return _servidor("127.0.0.1")


@pytest.fixture()
def client_remoto():
    """Um pedido vindo da rede local — o celular, ou qualquer coisa na casa."""
    return _servidor("192.168.0.10")


def evento(**payload) -> dict:
    base = {"sessionId": "sessao-1", "provider": "netflix"}
    return {
        "protocolVersion": 1,
        "messageType": "POSITION_SYNC",
        # A ponte manda milissegundos; o servidor conta em segundos.
        "timestamp": time.time() * 1000,
        "payload": {**base, **payload},
    }


# ── Credencial ────────────────────────────────────────────────────────────


def test_com_a_credencial_correta_o_evento_entra(client, segredo):
    resposta = client.post(
        "/bridge/eventos", json=evento(currentTime=10.0, duration=100.0),
        headers={CABECALHO: segredo},
    )

    assert resposta.status_code == 202
    assert resposta.json()["accepted"] == "POSITION_SYNC"


def test_sem_credencial_nenhuma_o_evento_e_recusado(client, segredo):
    resposta = client.post("/bridge/eventos", json=evento())

    assert resposta.status_code == 401


def test_com_a_credencial_errada_o_evento_e_recusado(client, segredo):
    resposta = client.post(
        "/bridge/eventos", json=evento(), headers={CABECALHO: "nao-e-o-segredo"},
    )

    assert resposta.status_code == 401


def test_ausente_e_errada_dao_a_mesma_resposta(client, segredo):
    """Distinguir as duas conta a quem tenta que o caminho está certo e falta só
    o segredo."""
    sem = client.post("/bridge/eventos", json=evento())
    errada = client.post(
        "/bridge/eventos", json=evento(), headers={CABECALHO: "chute"},
    )

    assert (sem.status_code, sem.json()) == (errada.status_code, errada.json())


def test_a_resposta_de_recusa_nao_ecoa_o_que_foi_apresentado(client, segredo):
    resposta = client.post(
        "/bridge/eventos", json=evento(), headers={CABECALHO: "chute-secreto"},
    )

    assert "chute-secreto" not in resposta.text
    assert segredo not in resposta.text


def test_sem_credencial_no_disco_nem_o_host_entra(client, tmp_path, monkeypatch):
    """Modo de falha fechado. Um arquivo apagado deixa a ponte muda."""
    monkeypatch.setattr(bridge, "credencial", CredencialDaPonte(tmp_path / "nao-existe"))

    resposta = client.post(
        "/bridge/eventos", json=evento(), headers={CABECALHO: "qualquer-coisa"},
    )

    assert resposta.status_code == 401


def test_a_credencial_e_conferida_em_toda_mensagem(client, segredo):
    """Não há sessão nem memória de quem já passou: a primeira ter dado certo
    não abre a porta para a segunda."""
    boa = client.post("/bridge/eventos", json=evento(), headers={CABECALHO: segredo})
    depois = client.post("/bridge/eventos", json=evento())

    assert boa.status_code == 202
    assert depois.status_code == 401


# ── Loopback e navegador ──────────────────────────────────────────────────


def test_um_pedido_de_fora_da_maquina_nao_existe(client_remoto, segredo):
    """404 e não 403: para quem está fora, esta rota não existe. Um 403
    confirmaria o endereço e o nome do endpoint.

    E repare que ele traz a credencial CERTA: nem o segredo abre a porta para
    quem não está na máquina."""
    resposta = client_remoto.post(
        "/bridge/eventos", json=evento(), headers={CABECALHO: segredo},
    )

    assert resposta.status_code == 404


def test_o_endereco_de_fora_e_recusado_antes_da_credencial(client_remoto, segredo):
    """A ordem importa: conferir a credencial primeiro daria a um pedido remoto
    uma forma de descobrir se ele acertou o segredo — a resposta seria 401 para
    o chute e 202 para o acerto."""
    resposta = client_remoto.post(
        "/bridge/eventos", json=evento(), headers={CABECALHO: "chute"},
    )

    assert resposta.status_code == 404


def test_uma_aba_do_navegador_nao_alcanca_a_rota(client, segredo):
    """Qualquer página aberta consegue fazer `fetch` para `127.0.0.1` — foi esse
    achado que descartou o WebSocket em localhost. O que ela NÃO consegue é
    omitir o `Origin`."""
    resposta = client.post(
        "/bridge/eventos", json=evento(),
        headers={CABECALHO: segredo, "origin": "https://www.netflix.com"},
    )

    assert resposta.status_code == 404


def test_nem_com_a_origem_do_proprio_controlfawkes(client, segredo):
    """Nem a origem do próprio painel. Esta rota não é para navegador nenhum."""
    resposta = client.post(
        "/bridge/eventos", json=evento(),
        headers={CABECALHO: segredo, "origin": "http://localhost:5173"},
    )

    assert resposta.status_code == 404


# ── A validação da Fase 6, inteira ────────────────────────────────────────


def test_autenticar_nao_e_confiar(client, segredo):
    """A regra do Master Loop, literal: a extensão não é fonte confiável só
    porque é nossa. Ela lê um DOM que ninguém aqui controla."""
    resposta = client.post(
        "/bridge/eventos",
        json=evento(currentTime=500.0, duration=100.0),
        headers={CABECALHO: segredo},
    )

    assert resposta.status_code == 422
    assert resposta.json()["detail"]["code"] == "IMPOSSIBLE_POSITION"


@pytest.mark.parametrize(
    ("mensagem", "codigo"),
    [
        ({"protocolVersion": 99, "messageType": "PLAY", "timestamp": 0,
          "payload": {"sessionId": "s"}}, "PROTOCOL_VERSION_MISMATCH"),
        ({"protocolVersion": 1, "messageType": "INVENTADO", "timestamp": 0,
          "payload": {"sessionId": "s"}}, "UNKNOWN_MESSAGE_TYPE"),
        ({"protocolVersion": 1, "messageType": "PLAY", "timestamp": 0,
          "payload": {"sessionId": ""}}, "INVALID_SESSION_ID"),
        ({"protocolVersion": 1, "messageType": "PLAY", "timestamp": 0,
          "payload": {"sessionId": "s", "tabId": True}}, "INVALID_TAB_ID"),
        ({"protocolVersion": 1, "messageType": "PLAY", "timestamp": 0,
          "payload": {"sessionId": "s", "playbackState": "buffering"}},
         "INVALID_PLAYBACK_STATE"),
        ({"protocolVersion": 1, "messageType": "PLAY", "timestamp": 0,
          "payload": "não é objeto"}, "INVALID_PAYLOAD"),
    ],
)
def test_cada_recusa_da_fase_6_continua_valendo(client, segredo, mensagem, codigo):
    resposta = client.post(
        "/bridge/eventos", json=mensagem, headers={CABECALHO: segredo},
    )

    assert resposta.status_code == 422
    assert resposta.json()["detail"]["code"] == codigo


def test_um_corpo_que_nao_e_json_nao_estoura(client, segredo):
    resposta = client.post(
        "/bridge/eventos", content=b"{isto nao e json",
        headers={CABECALHO: segredo, "content-type": "application/json"},
    )

    assert resposta.status_code == 400


def test_um_corpo_que_nao_e_objeto_e_recusado(client, segredo):
    resposta = client.post(
        "/bridge/eventos", json=[1, 2, 3], headers={CABECALHO: segredo},
    )

    assert resposta.status_code == 422
    assert resposta.json()["detail"]["code"] == "INVALID_MESSAGE"


def test_a_recusa_por_conteudo_e_diferente_da_recusa_por_credencial(client, segredo):
    """422 contra 401. Um host mal configurado e um host mandando lixo são
    problemas diferentes, e quem lê o log precisa distinguir os dois."""
    sem_credencial = client.post("/bridge/eventos", json=evento())
    conteudo_ruim = client.post(
        "/bridge/eventos", json=evento(currentTime=500.0, duration=100.0),
        headers={CABECALHO: segredo},
    )

    assert sem_credencial.status_code == 401
    assert conteudo_ruim.status_code == 422


# ── A rota não faz trabalho de fase futura ────────────────────────────────


def test_a_rota_aceita_e_para_por_ai(client, segredo):
    """Nem histórico, nem merger, nem relógio. Uma rota que já mexesse no
    histórico seria a Fase 12 acontecendo por acidente."""
    corpo = client.post(
        "/bridge/eventos", json=evento(currentTime=10.0, duration=100.0),
        headers={CABECALHO: segredo},
    ).json()

    assert corpo == {"ok": True, "accepted": "POSITION_SYNC", "sessionId": "sessao-1"}
