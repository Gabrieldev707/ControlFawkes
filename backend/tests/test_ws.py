import pytest
from fastapi.testclient import TestClient

from app.api import websocket as websocket_module
from app.main import app
from app.protocol.dispatcher import Dispatcher
from app.security.device_store import DeviceStore
from app.security.pairing import PairingService


@pytest.fixture
def dispatcher(tmp_path, monkeypatch):
    store = DeviceStore(
        filepath=tmp_path / "paired_devices.json",
        lockpath=tmp_path / "paired_devices.lock",
    )
    instance = Dispatcher(device_store=store, pairing_service=PairingService(store))
    monkeypatch.setattr(websocket_module, "dispatcher", instance)
    return instance


@pytest.fixture
def client(dispatcher):
    with TestClient(app) as test_client:
        yield test_client


def receive_auth_required(websocket):
    message = websocket.receive_json()
    assert message == {
        "protocolVersion": 1,
        "type": "STATE_UPDATE",
        "state": "AUTH_REQUIRED",
        "message": "Autenticação necessária.",
    }


def pair(websocket, dispatcher, request_id="pair-1"):
    websocket.send_json({
        "protocolVersion": 1,
        "type": "PAIR_DEVICE",
        "requestId": request_id,
        "payload": {
            "pin": dispatcher.pairing_service.current_pin,
            "deviceName": "iPhone",
        },
    })
    result = websocket.receive_json()
    ready = websocket.receive_json()
    assert result["type"] == "PAIR_RESULT"
    assert result["success"] is True
    assert ready["state"] == "READY"
    return result


def test_websocket_connection_requires_authentication(client):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)


def test_websocket_invalid_json(client):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        websocket.send_text("{ quebrado ")

        data = websocket.receive_json()

        assert data["protocolVersion"] == 1
        assert data["type"] == "ERROR"
        assert data["code"] == "INVALID_JSON"


@pytest.mark.parametrize("protocol_version", [None, 2, "1", True, 1.0])
def test_websocket_rejects_missing_or_invalid_protocol_version(client, protocol_version):
    message = {
        "type": "AUTH",
        "requestId": "auth-1",
        "payload": {"deviceId": "device-1", "token": "token-value"},
    }
    if protocol_version is not None:
        message["protocolVersion"] = protocol_version

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        websocket.send_json(message)

        data = websocket.receive_json()

        assert data["code"] == "PROTOCOL_VERSION_MISMATCH"


def test_websocket_rejects_unsupported_message(client):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "MAGIC_SPELL",
            "requestId": "req-1",
            "payload": {},
        })

        assert websocket.receive_json()["code"] == "UNSUPPORTED_MESSAGE"


def test_websocket_rejects_extra_fields(client):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "PAIR_DEVICE",
            "requestId": "req-1",
            "payload": {"pin": "123456", "deviceName": "iPhone", "extra": True},
        })

        assert websocket.receive_json()["code"] == "INVALID_PAYLOAD"


def test_websocket_rejects_unauthenticated_commands(client):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "TEXT_COMMAND",
            "requestId": "req-1",
            "payload": {"query": "ajuda"},
        })

        assert websocket.receive_json()["code"] == "UNAUTHORIZED"


def test_websocket_pairs_with_correct_pin(client, dispatcher):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)

        result = pair(websocket, dispatcher)

        assert result["protocolVersion"] == 1
        assert result["requestId"] == "pair-1"
        assert result["deviceId"]
        assert result["token"]


def test_websocket_rejects_incorrect_pin(client, dispatcher):
    invalid_pin = "000000" if dispatcher.pairing_service.current_pin != "000000" else "111111"
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "PAIR_DEVICE",
            "requestId": "pair-1",
            "payload": {"pin": invalid_pin, "deviceName": "iPhone"},
        })

        data = websocket.receive_json()

        assert data["type"] == "ERROR"
        assert data["code"] == "PIN_INVALID"


def test_websocket_authenticates_valid_token(client, dispatcher):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        credentials = pair(websocket, dispatcher)

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "AUTH",
            "requestId": "auth-1",
            "payload": {
                "deviceId": credentials["deviceId"],
                "token": credentials["token"],
            },
        })

        result = websocket.receive_json()
        ready = websocket.receive_json()

        assert result["type"] == "AUTH_RESULT"
        assert result["success"] is True
        assert ready["state"] == "READY"


def test_websocket_rejects_invalid_and_revoked_tokens(client, dispatcher):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        credentials = pair(websocket, dispatcher)

    dispatcher.device_store.revoke(credentials["deviceId"])

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "AUTH",
            "requestId": "auth-1",
            "payload": {
                "deviceId": credentials["deviceId"],
                "token": credentials["token"],
            },
        })

        data = websocket.receive_json()

        assert data["type"] == "ERROR"
        assert data["code"] == "INVALID_TOKEN"


def test_authenticated_platform_is_recognized_without_execution(client, dispatcher):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "PLATFORM_SELECTED",
            "requestId": "platform-1",
            "payload": {"platform": "NETFLIX"},
        })

        data = websocket.receive_json()

        assert data["type"] == "COMMAND_RESULT"
        assert data["requestId"] == "platform-1"
        assert data["success"] is True
        assert data["data"] == {
            "intent": "OPEN_PLATFORM",
            "platform": "NETFLIX",
            "executed": False,
        }


def test_authenticated_invalid_platform_is_rejected(client, dispatcher):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "PLATFORM_SELECTED",
            "requestId": "platform-1",
            "payload": {"platform": "UOL"},
        })

        assert websocket.receive_json()["code"] == "INVALID_PAYLOAD"


def test_health_endpoint_remains_available(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "fawkes-remote"}


def test_authenticated_known_text_command_is_recognized_without_execution(client, dispatcher):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "TEXT_COMMAND",
            "requestId": "text-1",
            "payload": {"query": "abre o Spotify"},
        })

        busy = websocket.receive_json()
        result = websocket.receive_json()
        ready = websocket.receive_json()

        assert busy["state"] == "BUSY"
        assert result == {
            "protocolVersion": 1,
            "type": "COMMAND_RESULT",
            "requestId": "text-1",
            "success": True,
            "message": "Comando reconhecido: abrir Spotify.",
            "data": {
                "intent": "OPEN_PLATFORM",
                "platform": "SPOTIFY",
                "executed": False,
            },
        }
        assert ready["state"] == "READY"


def test_authenticated_help_command_returns_supported_examples(client, dispatcher):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "TEXT_COMMAND",
            "requestId": "text-1",
            "payload": {"query": "o que você faz"},
        })

        websocket.receive_json()
        result = websocket.receive_json()
        websocket.receive_json()

        assert result["type"] == "COMMAND_RESULT"
        assert result["data"]["intent"] == "SHOW_HELP"
        assert result["data"]["executed"] is False
        assert "abre netflix" in result["data"]["commands"]


def test_authenticated_unknown_text_command_returns_clear_error(client, dispatcher):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "TEXT_COMMAND",
            "requestId": "text-1",
            "payload": {"query": "escolhe um filme"},
        })

        busy = websocket.receive_json()
        error = websocket.receive_json()
        ready = websocket.receive_json()

        assert busy["state"] == "BUSY"
        assert error["type"] == "ERROR"
        assert error["requestId"] == "text-1"
        assert error["code"] == "UNKNOWN_COMMAND"
        assert error["message"] == "Não entendi esse comando."
        assert ready["state"] == "READY"
