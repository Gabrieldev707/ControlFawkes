import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_websocket_connection():
    with client.websocket_connect("/ws") as websocket:
        # 1. Verifica estado inicial enviado pelo servidor
        data = websocket.receive_json()
        assert data["type"] == "STATE_UPDATE"
        assert data["state"] == "connected"

def test_websocket_invalid_json():
    with client.websocket_connect("/ws") as websocket:
        websocket.receive_json() # descarta initial state

        # Envia json quebrado
        websocket.send_text("{ quebrado ")
        data = websocket.receive_json()

        assert data["type"] == "ERROR"
        assert data["code"] == "INVALID_JSON"

def test_websocket_non_object_payload():
    with client.websocket_connect("/ws") as websocket:
        websocket.receive_json()

        # Envia array
        websocket.send_text("[]")
        data = websocket.receive_json()
        assert data["type"] == "ERROR"
        assert data["code"] == "INVALID_PAYLOAD"

        # Envia null
        websocket.send_text("null")
        data = websocket.receive_json()
        assert data["type"] == "ERROR"
        assert data["code"] == "INVALID_PAYLOAD"

        # Envia string
        websocket.send_text('"texto"')
        data = websocket.receive_json()
        assert data["type"] == "ERROR"
        assert data["code"] == "INVALID_PAYLOAD"

        # Envia number
        websocket.send_text("123")
        data = websocket.receive_json()
        assert data["type"] == "ERROR"
        assert data["code"] == "INVALID_PAYLOAD"

def test_websocket_unsupported_message():
    with client.websocket_connect("/ws") as websocket:
        websocket.receive_json()

        # Envia payload com type inexistente
        websocket.send_json({
            "type": "MAGIC_SPELL",
            "requestId": "123",
            "payload": {}
        })
        data = websocket.receive_json()

        assert data["type"] == "ERROR"
        assert data["code"] == "UNSUPPORTED_MESSAGE"

def test_websocket_invalid_payload():
    with client.websocket_connect("/ws") as websocket:
        websocket.receive_json()

        # Envia type conhecido com payload errado
        websocket.send_json({
            "type": "PLATFORM_SELECTED",
            "requestId": "123",
            "payload": {
                "platform": "UOL" # Invalido
            }
        })
        data = websocket.receive_json()

        assert data["type"] == "ERROR"
        assert data["code"] == "INVALID_PAYLOAD"

def test_websocket_missing_request_id():
    with client.websocket_connect("/ws") as websocket:
        websocket.receive_json()

        # Envia sem requestId
        websocket.send_json({
            "type": "PLATFORM_SELECTED",
            "payload": {
                "platform": "NETFLIX"
            }
        })
        data = websocket.receive_json()

        assert data["type"] == "ERROR"
        assert data["code"] == "INVALID_PAYLOAD"

def test_websocket_extra_fields():
    with client.websocket_connect("/ws") as websocket:
        websocket.receive_json()

        # Envia com campo extra
        websocket.send_json({
            "type": "PLATFORM_SELECTED",
            "requestId": "req-1",
            "extra_field": "hack",
            "payload": {
                "platform": "NETFLIX"
            }
        })
        data = websocket.receive_json()

        assert data["type"] == "ERROR"
        assert data["code"] == "INVALID_PAYLOAD"

def test_websocket_platform_selected():
    with client.websocket_connect("/ws") as websocket:
        websocket.receive_json()

        # Envia plataforma valida
        websocket.send_json({
            "type": "PLATFORM_SELECTED",
            "requestId": "req-1",
            "payload": {
                "platform": "NETFLIX"
            }
        })
        data = websocket.receive_json()

        assert data["type"] == "COMMAND_RESULT"
        assert data["requestId"] == "req-1"
        assert data["success"] is True
        assert data["data"]["platform"] == "NETFLIX"

def test_websocket_unimplemented_handler():
    with client.websocket_connect("/ws") as websocket:
        websocket.receive_json()

        # Envia comando válido mas que ainda não tem handler em Phase 1.5
        websocket.send_json({
            "type": "TEXT_COMMAND",
            "requestId": "req-2",
            "payload": {
                "query": "hello"
            }
        })
        data = websocket.receive_json()

        assert data["type"] == "ERROR"
        assert data["code"] == "NOT_IMPLEMENTED"
