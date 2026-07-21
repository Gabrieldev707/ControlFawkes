import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, call

from app.api import websocket as websocket_module
from app.main import app
from app.protocol.dispatcher import Dispatcher
from app.security.device_store import DeviceStore
from app.security.pairing import PairingService
from app.media.windows_adapter import WindowsMediaAdapter


@pytest.fixture
def browser_open_mock(monkeypatch):
    opener = Mock(return_value=True)
    monkeypatch.setattr("webbrowser.open", opener)
    return opener


@pytest.fixture
def windows_key_event_mock(monkeypatch):
    emitter = Mock()
    monkeypatch.setattr("ctypes.windll.user32.keybd_event", emitter)
    return emitter


@pytest.fixture
def dispatcher(tmp_path, monkeypatch, browser_open_mock, windows_key_event_mock):
    store = DeviceStore(
        filepath=tmp_path / "paired_devices.json",
        lockpath=tmp_path / "paired_devices.lock",
    )
    instance = Dispatcher(
        device_store=store,
        pairing_service=PairingService(store),
        media_adapter=WindowsMediaAdapter(windows_key_event_mock),
    )
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


def test_websocket_rejects_unauthenticated_media_control(client):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "MEDIA_PLAY_PAUSE",
            "requestId": "media-1",
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


@pytest.mark.parametrize(
    ("platform", "label", "url"),
    [
        ("YOUTUBE", "YouTube", "https://www.youtube.com"),
        ("NETFLIX", "Netflix", "https://www.netflix.com"),
        ("MAX", "Max", "https://www.max.com"),
        ("PRIME_VIDEO", "Prime Video", "https://www.primevideo.com"),
        ("DISNEY_PLUS", "Disney+", "https://www.disneyplus.com"),
    ],
)
def test_authenticated_streaming_selection_opens_only_the_official_url(
    client,
    dispatcher,
    browser_open_mock,
    platform,
    label,
    url,
):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "PLATFORM_SELECTED",
            "requestId": "platform-1",
            "payload": {"platform": platform},
        })

        result = websocket.receive_json()

        assert result == {
            "protocolVersion": 1,
            "type": "COMMAND_RESULT",
            "requestId": "platform-1",
            "success": True,
            "message": f"{label} aberto.",
            "data": {
                "intent": "OPEN_PLATFORM",
                "platform": platform,
                "executed": True,
            },
        }
        browser_open_mock.assert_called_once_with(url, new=2, autoraise=True)


def test_authenticated_spotify_selection_opens_only_the_official_url(
    client,
    dispatcher,
    browser_open_mock,
):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "PLATFORM_SELECTED",
            "requestId": "platform-spotify",
            "payload": {"platform": "SPOTIFY"},
        })

        result = websocket.receive_json()

        assert result == {
            "protocolVersion": 1,
            "type": "COMMAND_RESULT",
            "requestId": "platform-spotify",
            "success": True,
            "message": "Spotify aberto.",
            "data": {
                "intent": "OPEN_PLATFORM",
                "platform": "SPOTIFY",
                "executed": True,
            },
        }
        browser_open_mock.assert_called_once_with(
            "https://open.spotify.com",
            new=2,
            autoraise=True,
        )


@pytest.mark.parametrize(
    ("platform", "label"),
    [
        ("SPOTIFY", "Spotify"),
        ("YOUTUBE", "YouTube"),
        ("NETFLIX", "Netflix"),
        ("MAX", "Max"),
        ("PRIME_VIDEO", "Prime Video"),
        ("DISNEY_PLUS", "Disney+"),
    ],
)
def test_platform_open_failure_returns_a_real_error(
    client,
    dispatcher,
    browser_open_mock,
    platform,
    label,
):
    browser_open_mock.return_value = False

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "PLATFORM_SELECTED",
            "requestId": "platform-1",
            "payload": {"platform": platform},
        })

        error = websocket.receive_json()

        assert error == {
            "protocolVersion": 1,
            "type": "ERROR",
            "requestId": "platform-1",
            "code": "PLATFORM_OPEN_FAILED",
            "message": f"Não foi possível abrir o {label}.",
        }


def test_platform_selection_rejects_a_frontend_supplied_url(
    client,
    dispatcher,
    browser_open_mock,
):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "PLATFORM_SELECTED",
            "requestId": "platform-spotify",
            "payload": {
                "platform": "SPOTIFY",
                "url": "https://example.com/not-allowed",
            },
        })

        assert websocket.receive_json()["code"] == "INVALID_PAYLOAD"
        browser_open_mock.assert_not_called()


@pytest.mark.parametrize(
    ("action", "virtual_key", "message"),
    [
        ("MEDIA_PLAY_PAUSE", 0xB3, "Play/pause executado."),
        ("MEDIA_PREVIOUS", 0xB1, "Faixa anterior executada."),
        ("MEDIA_NEXT", 0xB0, "Próxima faixa executada."),
        ("MEDIA_SEEK_BACK", 0x25, "Retrocesso de 10 segundos executado."),
        ("MEDIA_SEEK_FORWARD", 0x27, "Avanço de 10 segundos executado."),
        ("MEDIA_FULLSCREEN", 0x7A, "Fullscreen executado."),
        ("MEDIA_EXIT_FULLSCREEN", 0x1B, "Saída do fullscreen executada."),
    ],
)
def test_authenticated_media_control_uses_only_allowlisted_windows_keys(
    client,
    dispatcher,
    windows_key_event_mock,
    action,
    virtual_key,
    message,
):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": action,
            "requestId": "media-1",
        })

        result = websocket.receive_json()

        assert result == {
            "protocolVersion": 1,
            "type": "COMMAND_RESULT",
            "requestId": "media-1",
            "success": True,
            "message": message,
            "data": {
                "intent": "MEDIA_CONTROL",
                "action": action,
                "executed": True,
            },
        }
        assert windows_key_event_mock.call_args_list == [
            call(virtual_key, 0, 0, 0),
            call(virtual_key, 0, 2, 0),
        ]


def test_media_control_rejects_arbitrary_key_payload(
    client,
    dispatcher,
    windows_key_event_mock,
):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "MEDIA_PLAY_PAUSE",
            "requestId": "media-1",
            "payload": {"key": "A"},
        })

        assert websocket.receive_json()["code"] == "INVALID_PAYLOAD"
        windows_key_event_mock.assert_not_called()


def test_media_control_reports_adapter_failure(
    client,
    dispatcher,
    windows_key_event_mock,
):
    windows_key_event_mock.side_effect = OSError("Windows input unavailable")

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "MEDIA_PLAY_PAUSE",
            "requestId": "media-1",
        })

        error = websocket.receive_json()

        assert error["code"] == "MEDIA_CONTROL_FAILED"
        assert error["message"] == "Controle de mídia indisponível."


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


def test_authenticated_spotify_text_command_is_executed(
    client,
    dispatcher,
    browser_open_mock,
):
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
            "message": "Spotify aberto.",
            "data": {
                "intent": "OPEN_PLATFORM",
                "platform": "SPOTIFY",
                "executed": True,
            },
        }
        assert ready["state"] == "READY"
        browser_open_mock.assert_called_once_with(
            "https://open.spotify.com",
            new=2,
            autoraise=True,
        )


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
