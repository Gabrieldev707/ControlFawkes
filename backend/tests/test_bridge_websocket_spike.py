"""Spike B da Fase 1 — WebSocket local autenticado.

A pergunta que este spike responde não é "dá para conectar?". Dá. É:

    Reutilizar o modelo de confiança que já existe custa o quê?

O Master Loop proíbe criar um segundo modelo de confiança. Então o spike mede
exatamente o quanto o modelo atual acomoda uma extensão — e o que quebra ao
tentar acomodá-la.

Não usa Chrome: origem de WebSocket é um cabeçalho, e é isso que a política lê.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from app.api import websocket as websocket_module
from app.history.recorder import HistoryRecorder
from app.history.store import HistoryStore
from app.main import app
from app.protocol.dispatcher import Dispatcher
from app.security.device_store import DeviceStore
from app.security.origins import ALLOWED_ORIGINS_VARIABLE, is_origin_allowed
from app.security.pairing import PairingService


EXTENSAO = "chrome-extension://bbnnlajckbgplcfoeabclhkoilboccaf"


@pytest.fixture
def dispatcher(tmp_path, monkeypatch):
    """Um dispatcher de verdade, com o mundo externo desligado.

    O leitor de mídia é falso de propósito: este spike verifica autenticação,
    e deixar o laço de "tocando agora" tocar o Windows tornaria o teste
    dependente do que estiver aberto na máquina.
    """
    store = DeviceStore(
        filepath=tmp_path / "paired_devices.json",
        lockpath=tmp_path / "paired_devices.lock",
    )
    leitor = Mock()
    leitor.read = AsyncMock(return_value=None)

    instancia = Dispatcher(
        device_store=store,
        pairing_service=PairingService(store),
        now_playing_reader=leitor,
        history_recorder=HistoryRecorder(HistoryStore(tmp_path / "historico.json")),
        catalog=None,
    )
    monkeypatch.setattr(websocket_module, "dispatcher", instancia)
    return instancia


@pytest.fixture
def client(dispatcher):
    with TestClient(app) as test_client:
        yield test_client


# ── O que a política de origem faz hoje ───────────────────────────────────


def test_a_origem_de_uma_extensao_e_recusada_hoje():
    """Achado do spike: a extensão NÃO passa pela política atual.

    `is_origin_allowed` exige esquema `http`/`https`. Uma extensão se apresenta
    como `chrome-extension://<id>`, então é recusada antes de qualquer token
    ser olhado.

    Isso não é defeito: é a política fazendo o trabalho dela. É o CUSTO do
    transporte por WebSocket, e ele precisa estar medido antes da decisão.
    """
    assert is_origin_allowed(EXTENSAO) is False


def test_um_site_remoto_continua_sendo_barrado():
    """A defesa que a política realmente entrega: o ataque drive-by.

    Um site remoto não consegue forjar Origin, então bloquear origem não-local
    elimina a página maliciosa que tenta abrir um socket no computador de quem
    a visita.
    """
    assert is_origin_allowed("https://exemplo.com") is False
    assert is_origin_allowed("null") is False


def test_qualquer_pagina_local_passa_pela_origem():
    """E aqui está o limite do que a origem protege.

    Qualquer coisa servida de localhost — um projeto em desenvolvimento na
    porta 3000, um servidor de arquivos, qualquer página aberta pelo próprio
    usuário — passa. A origem NÃO é a defesa contra ela; quem defende é o
    pareamento.

    Isto importa para a decisão: um WebSocket local é alcançável por muito mais
    coisa do que um canal que o Chrome só entrega a um ID declarado.
    """
    assert is_origin_allowed("http://localhost:3000") is True
    assert is_origin_allowed("http://192.168.0.14:5173") is True


def test_cliente_sem_origem_passa_de_proposito():
    """Um cliente nativo pode omitir ou falsificar o cabeçalho. Recusar a
    ausência não impediria ninguém e quebraria clientes legítimos — quem
    defende contra ele é o pareamento."""
    assert is_origin_allowed(None) is True


# ── O custo de acomodar a extensão ────────────────────────────────────────


def test_liberar_a_extensao_pela_variavel_de_ambiente_quebra_o_celular(monkeypatch):
    """O achado que decide o spike.

    `FAWKES_ALLOWED_ORIGINS` não ACRESCENTA à política: ele a SUBSTITUI por uma
    lista fechada. Pôr a extensão ali derruba o celular no mesmo instante,
    porque a origem do celular é o IP da LAN — que muda com a rede, com o DHCP
    e com o aparelho.

    Ou seja: a saída "é só configurar uma variável" custa enumerar à mão toda
    origem legítima, para sempre. Não é reutilizar o modelo de confiança
    existente; é aposentá-lo.
    """
    monkeypatch.setenv(ALLOWED_ORIGINS_VARIABLE, EXTENSAO)

    assert is_origin_allowed(EXTENSAO) is True
    # E o celular, que funcionava, para de funcionar.
    assert is_origin_allowed("http://192.168.0.14:5173") is False
    assert is_origin_allowed("http://localhost:5173") is False


def test_a_alternativa_seria_uma_mudanca_dirigida_na_politica():
    """A outra saída é aceitar `chrome-extension://<id-exato>` na própria
    política, ao lado das origens locais.

    Este teste documenta que ela NÃO existe hoje — e serve de sino se alguém a
    implementar sem passar pela decisão de arquitetura.

    Custo dela: a política passa a conhecer um ID de extensão, ou seja, o
    ControlFawkes passa a ter uma lista de extensões confiáveis. É um modelo de
    confiança novo, mesmo que pequeno — exatamente o que o Master Loop manda
    evitar sem necessidade comprovada.
    """
    assert is_origin_allowed(f"{EXTENSAO}/") is False


# ── O pareamento, que é a defesa de verdade ───────────────────────────────


def test_sem_token_nao_se_faz_nada(client):
    """Origem permitida não é autorização. Sem AUTH, o socket não opera."""
    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_json()["state"] == "AUTH_REQUIRED"

        websocket.send_json({
            "protocolVersion": 1,
            "type": "TEXT_COMMAND",
            "requestId": "sem-token-1",
            "payload": {"query": "pausar"},
        })

        assert websocket.receive_json()["code"] == "UNAUTHORIZED"


def test_token_invalido_e_recusado(client):
    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_json()["state"] == "AUTH_REQUIRED"

        websocket.send_json({
            "protocolVersion": 1,
            "type": "AUTH",
            "requestId": "auth-ruim",
            # 16 caracteres no mínimo, ou o esquema recusa ANTES da
            # autenticação e o erro vira "payload inválido" — que diz outra
            # coisa para quem está do outro lado.
            "payload": {"deviceId": "nao-existe", "token": "x" * 32},
        })

        resposta = websocket.receive_json()

        # Token inválido não vira "AUTH_RESULT com success=false": `success` é
        # `Literal[True]` no esquema, então falha SEMPRE vira ERROR.
        #
        # E o código distingue os três casos, que é o que a extensão precisa
        # para não entrar em laço de pareamento:
        #   INVALID_PAYLOAD  formato errado
        #   INVALID_TOKEN    par deviceId/token não confere
        #   UNAUTHORIZED     tentou operar sem ter autenticado
        assert resposta["type"] == "ERROR"
        assert resposta["code"] == "INVALID_TOKEN"


def test_o_esquema_e_validado_antes_da_autenticacao(client):
    """Ordem que importa para o desenho da extensão.

    Um token curto demais não devolve UNAUTHORIZED: devolve INVALID_PAYLOAD,
    porque o esquema roda antes. Uma extensão que trate os dois como "preciso
    parear de novo" entraria num laço de pareamento por causa de um bug de
    formato.
    """
    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_json()["state"] == "AUTH_REQUIRED"

        websocket.send_json({
            "protocolVersion": 1,
            "type": "AUTH",
            "requestId": "auth-curto",
            "payload": {"deviceId": "d", "token": "curto"},
        })

        assert websocket.receive_json()["code"] == "INVALID_PAYLOAD"


def test_o_token_provisionado_pelo_pareamento_e_aceito(client, dispatcher):
    """O caminho que a extensão teria de percorrer para guardar um token em
    `chrome.storage`: o MESMO pareamento por PIN do celular.

    E é aqui que aparece a fricção do Spike B: o PIN é mostrado no console do
    servidor e expira em 5 minutos. Uma extensão que precise dele passa a
    depender de o usuário ler o terminal e digitar em algum lugar — para um
    componente que deveria simplesmente estar instalado.
    """
    pin = dispatcher.pairing_service.current_pin

    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_json()["state"] == "AUTH_REQUIRED"

        websocket.send_json({
            "protocolVersion": 1,
            "type": "PAIR_DEVICE",
            "requestId": "pair-extensao",
            "payload": {"pin": pin, "deviceName": "Browser Media Bridge"},
        })

        resultado = websocket.receive_json()

        assert resultado["success"] is True
        assert resultado["token"]
        assert resultado["deviceId"]

    # E o token vale numa conexão nova — que é o caso do restart do navegador.
    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_json()["state"] == "AUTH_REQUIRED"

        websocket.send_json({
            "protocolVersion": 1,
            "type": "AUTH",
            "requestId": "auth-extensao",
            "payload": {
                "deviceId": resultado["deviceId"],
                "token": resultado["token"],
            },
        })

        confirmacao = websocket.receive_json()

        assert confirmacao["type"] == "AUTH_RESULT"
        assert confirmacao["success"] is True


def test_o_token_sobrevive_a_um_restart_do_controlfawkes(tmp_path):
    """O token fica em disco, não em memória: reiniciar o servidor não
    desemparelha ninguém — nem o celular, nem a extensão."""
    caminho = tmp_path / "paired_devices.json"
    trava = tmp_path / "paired_devices.lock"

    antes = DeviceStore(filepath=caminho, lockpath=trava)
    assert antes.add("bridge-1", "Browser Media Bridge", "token-secreto") is True

    # Outra instância, como depois de reiniciar o processo.
    depois = DeviceStore(filepath=caminho, lockpath=trava)

    assert depois.authenticate("bridge-1", "token-secreto") is True
    assert depois.authenticate("bridge-1", "outro-token") is False
