import pytest
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)
def test_websocket_auth_required():
    with client.websocket_connect("/ws") as websocket:
        # Try to send VOLUME_GET without auth
        websocket.send_json({
            "type": "VOLUME_GET",
            "requestId": "req-1",
            "payload": {}
        })
        data = websocket.receive_json()
        assert data["type"] == "ERROR"
        assert data["code"] == "AUTH_REQUIRED"
        assert data["requestId"] == "req-1"
def test_websocket_pairing_flow():
    with client.websocket_connect("/ws") as websocket:
        # First send an invalid pin
        websocket.send_json({
            "type": "PAIR_DEVICE",
            "requestId": "req-pair-1",
            "payload": {"pin": "000000", "deviceName": "Test Device"}
        })
        data = websocket.receive_json()
        assert data["type"] == "PAIR_RESULT"
        assert data["success"] is False
        assert data["requestId"] == "req-pair-1"
def test_websocket_invalid_json():
    with client.websocket_connect("/ws") as websocket:
        # Send raw string
        websocket.send_text("Not a json")
        data = websocket.receive_json()
        assert data["type"] == "ERROR"
        assert data["code"] == "INVALID_JSON"
def test_websocket_large_payload():
    with client.websocket_connect("/ws") as websocket:
        # Send >8KB payload
        large_string = "a" * 8192
        websocket.send_json({
            "type": "AUTH",
            "requestId": "123",
            "payload": {"deviceId": "a", "token": large_string}
        })
        data = websocket.receive_json()
        assert data["type"] == "ERROR"
        assert data["code"] == "PAYLOAD_TOO_LARGE"
