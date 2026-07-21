import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.protocol.dispatcher import Dispatcher
import app.api.websocket as ws_api
from app.security.device_store import DeviceStore

@pytest.fixture
def mock_volume_service():
    mock_service = MagicMock()
    mock_service.get_state.return_value = (50, False)
    mock_service.set_level.return_value = (60, False)
    mock_service.step.return_value = (65, False)
    mock_service.toggle_mute.return_value = (65, True)
    
    # We need to make these return coroutines since they are awaited
    async def get_state_async(): return mock_service.get_state()
    async def set_level_async(lvl): return mock_service.set_level(lvl)
    async def step_async(d): return mock_service.step(d)
    async def toggle_mute_async(): return mock_service.toggle_mute()
    
    mock_async_service = MagicMock()
    mock_async_service.get_state = get_state_async
    mock_async_service.set_level = set_level_async
    mock_async_service.step = step_async
    mock_async_service.toggle_mute = toggle_mute_async
    return mock_async_service

@pytest.fixture
def e2e_client(mock_volume_service, tmp_path):
    # Reset dispatcher for clean state
    test_db = tmp_path / "test_paired_devices.json"
    test_lock = tmp_path / "test_paired_devices.lock"
    temp_store = DeviceStore(filepath=str(test_db), lockpath=str(test_lock))
    dispatcher = Dispatcher(device_store=temp_store)
    dispatcher.volume_service = mock_volume_service
    ws_api.dispatcher = dispatcher
    
    with TestClient(app) as client:
        yield client, dispatcher

def test_pin_available_at_startup(e2e_client):
    _, dispatcher = e2e_client
    pin = dispatcher.pairing_service.get_current_pin_for_test()
    assert pin is not None
    assert len(pin) == 6

def test_full_pairing_and_auth_flow(e2e_client):
    client, dispatcher = e2e_client
    pin = dispatcher.pairing_service.get_current_pin_for_test()
    
    with client.websocket_connect("/ws") as ws:
        # 1. Invalid PIN
        ws.send_json({
            "type": "PAIR_DEVICE",
            "requestId": "req-1",
            "payload": {"pin": "000000", "deviceName": "Test"}
        })
        res = ws.receive_json()
        assert res["type"] == "PAIR_RESULT"
        assert res["success"] is False
        
        # 2. Valid PIN -> successful pair
        ws.send_json({
            "type": "PAIR_DEVICE",
            "requestId": "req-2",
            "payload": {"pin": pin, "deviceName": "Test"}
        })
        res = ws.receive_json()
        assert res["type"] == "PAIR_RESULT"
        assert res["success"] is True
        token = res["token"]
        device_id = res["deviceId"]
        
        # 3. Disconnect and Reconnect using AUTH
    with client.websocket_connect("/ws") as ws:
        ws.send_json({
            "type": "AUTH",
            "requestId": "req-3",
            "payload": {"deviceId": device_id, "token": token}
        })
        res = ws.receive_json()
        assert res["type"] == "AUTH_RESULT"
        assert res["success"] is True
        
        # 4. Protected volume read
        ws.send_json({
            "type": "VOLUME_GET",
            "requestId": "req-4",
            "payload": {}
        })
        res = ws.receive_json()
        assert res["type"] == "VOLUME_STATE"
        assert res["level"] == 50
        
        # 5. Protected text command
        ws.send_json({
            "type": "TEXT_COMMAND",
            "requestId": "req-5",
            "payload": {"query": "hello"}
        })
        res = ws.receive_json()
        assert res["type"] == "COMMAND_RESULT"
        assert res["success"] is True

def test_invalid_auth_and_revocation(e2e_client):
    client, dispatcher = e2e_client
    pin = dispatcher.pairing_service.get_current_pin_for_test()
    
    with client.websocket_connect("/ws") as ws:
        ws.send_json({
            "type": "PAIR_DEVICE",
            "requestId": "req-2",
            "payload": {"pin": pin, "deviceName": "Test"}
        })
        res = ws.receive_json()
        token = res["token"]
        device_id = res["deviceId"]
        
    # Revoke
    dispatcher.device_store.revoke_device(device_id)
    
    with client.websocket_connect("/ws") as ws:
        # Auth fails
        ws.send_json({
            "type": "AUTH",
            "requestId": "req-3",
            "payload": {"deviceId": device_id, "token": token}
        })
        res = ws.receive_json()
        assert res["type"] == "AUTH_RESULT"
        assert res["success"] is False

def test_rate_limit_and_multiple_connections(e2e_client):
    client, dispatcher = e2e_client
    pin = dispatcher.pairing_service.get_current_pin_for_test()
    
    # Pair to get a token
    with client.websocket_connect("/ws") as ws:
        ws.send_json({
            "type": "PAIR_DEVICE",
            "requestId": "req-1",
            "payload": {"pin": pin, "deviceName": "Test"}
        })
        res = ws.receive_json()
        token = res["token"]
        device_id = res["deviceId"]

    # Connect with two different websockets
    with client.websocket_connect("/ws") as ws1, client.websocket_connect("/ws") as ws2:
        ws1.send_json({"type": "AUTH", "requestId": "1", "payload": {"deviceId": device_id, "token": token}})
        assert ws1.receive_json()["success"] is True
        
        ws2.send_json({"type": "AUTH", "requestId": "2", "payload": {"deviceId": device_id, "token": token}})
        assert ws2.receive_json()["success"] is True

        # Consume all rate limits on ws1
        for i in range(20):
            ws1.send_json({"type": "VOLUME_GET", "requestId": f"spam-{i}", "payload": {}})
            assert ws1.receive_json()["type"] == "VOLUME_STATE"
            
        # The 21st should fail for RATE_LIMITED (since they share the same device_id bucket)
        ws2.send_json({"type": "VOLUME_GET", "requestId": "spam-21", "payload": {}})
        res = ws2.receive_json()
        assert res["type"] == "ERROR"
        assert res["code"] == "RATE_LIMITED"
