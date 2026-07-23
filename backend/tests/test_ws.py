import ctypes

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock, call

from app.api import websocket as websocket_module
from app.main import app
from app.protocol.dispatcher import (
    WS_POLICY_VIOLATION,
    WS_TRY_AGAIN_LATER,
    Dispatcher,
)
from app.security.device_store import DeviceStore
from app.security.pairing import PairingService
from app.media.windows_adapter import WindowsMediaAdapter
from app.media.session import MediaSession, WindowsMediaSessionDetector
from app.windows.volume import VolumeState, WindowsVolumeAdapter, WindowsVolumeError
from app.input.pointer import PointerRateLimiter, WindowsPointerAdapter
from app.input.keyboard import WindowsKeyboardAdapter
from app.platforms.browser import BrowserLaunchResult, BrowserLauncher
from app.platforms.launcher import PlatformLauncher
from app.platforms.spotify import SpotifyLauncher
from app.platforms.search import MediaSearchLauncher


@pytest.fixture
def browser_launcher_mock():
    launcher = Mock(spec=BrowserLauncher)
    launcher.open.return_value = BrowserLaunchResult(executed=True, strategy="CHROME")
    return launcher


@pytest.fixture
def spotify_launcher_mock():
    launcher = Mock(spec=SpotifyLauncher)
    launcher.open.return_value = BrowserLaunchResult(
        executed=True,
        strategy="SPOTIFY_APP",
    )
    return launcher


@pytest.fixture
def media_search_launcher_mock():
    launcher = Mock(spec=MediaSearchLauncher)
    launcher.search.return_value = BrowserLaunchResult(
        executed=True,
        strategy="CHROME",
    )
    return launcher


@pytest.fixture
def windows_key_event_mock(monkeypatch):
    emitter = Mock()
    # O emitter é injetado nos adapters; o patch global é apenas a garantia de
    # que nenhuma tecla real seja emitida. Runners não-Windows (CI) não expõem
    # ctypes.windll, e lá os adapters já ficam inertes por sys.platform.
    windll = getattr(ctypes, "windll", None)
    if windll is not None:
        monkeypatch.setattr(windll.user32, "keybd_event", emitter)
    return emitter


@pytest.fixture
def media_session_detector_mock():
    detector = Mock(spec=WindowsMediaSessionDetector)
    detector.detect.return_value = MediaSession(platform="YOUTUBE", kind="WEB")
    return detector


@pytest.fixture
def volume_adapter_mock():
    adapter = AsyncMock(spec=WindowsVolumeAdapter)
    adapter.get_state.return_value = VolumeState(level=42, muted=False)
    adapter.set_level.return_value = VolumeState(level=73, muted=False)
    adapter.change_level.return_value = VolumeState(level=47, muted=False)
    adapter.toggle_mute.return_value = VolumeState(level=42, muted=True)
    return adapter


@pytest.fixture
def pointer_adapter_mock():
    adapter = Mock(spec=WindowsPointerAdapter)
    adapter.move.return_value = True
    adapter.click.return_value = True
    adapter.double_click.return_value = True
    adapter.right_click.return_value = True
    adapter.scroll.return_value = True
    adapter.pointer_down.return_value = True
    adapter.pointer_up.return_value = True
    return adapter


@pytest.fixture
def keyboard_adapter_mock():
    adapter = Mock(spec=WindowsKeyboardAdapter)
    adapter.write_text.return_value = True
    adapter.press_key.return_value = True
    return adapter


@pytest.fixture
def dispatcher(
    tmp_path,
    monkeypatch,
    browser_launcher_mock,
    spotify_launcher_mock,
    media_search_launcher_mock,
    windows_key_event_mock,
    media_session_detector_mock,
    volume_adapter_mock,
    pointer_adapter_mock,
    keyboard_adapter_mock,
):
    store = DeviceStore(
        filepath=tmp_path / "paired_devices.json",
        lockpath=tmp_path / "paired_devices.lock",
    )
    instance = Dispatcher(
        device_store=store,
        pairing_service=PairingService(store),
        platform_launcher=PlatformLauncher(
            browser_launcher=browser_launcher_mock,
            spotify_launcher=spotify_launcher_mock,
        ),
        media_search_launcher=media_search_launcher_mock,
        media_adapter=WindowsMediaAdapter(windows_key_event_mock),
        media_session_detector=media_session_detector_mock,
        volume_adapter=volume_adapter_mock,
        pointer_adapter=pointer_adapter_mock,
        pointer_rate_limiter=PointerRateLimiter(max_updates=60),
        keyboard_adapter=keyboard_adapter_mock,
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
    browser_launcher_mock,
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
                "strategy": "CHROME",
            },
        }
        browser_launcher_mock.open.assert_called_once_with(url)


def test_authenticated_spotify_selection_opens_only_the_official_url(
    client,
    dispatcher,
    spotify_launcher_mock,
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
                "strategy": "SPOTIFY_APP",
            },
        }
        spotify_launcher_mock.open.assert_called_once_with()


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
    browser_launcher_mock,
    spotify_launcher_mock,
    platform,
    label,
):
    if platform == "SPOTIFY":
        spotify_launcher_mock.open.return_value = BrowserLaunchResult(
            executed=False,
            error="SPOTIFY_LAUNCH_FAILED",
        )
    else:
        browser_launcher_mock.open.return_value = BrowserLaunchResult(
            executed=False,
            error="CHROME_LAUNCH_FAILED",
        )

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


def test_chrome_not_found_returns_a_specific_real_error(
    client,
    dispatcher,
    browser_launcher_mock,
):
    browser_launcher_mock.open.return_value = BrowserLaunchResult(
        executed=False,
        error="CHROME_NOT_FOUND",
    )

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "PLATFORM_SELECTED",
            "requestId": "platform-chrome",
            "payload": {"platform": "YOUTUBE"},
        })

        error = websocket.receive_json()

        assert error["code"] == "PLATFORM_OPEN_FAILED"
        assert error["message"] == "Google Chrome não foi encontrado no computador."


def test_platform_selection_rejects_a_frontend_supplied_url(
    client,
    dispatcher,
    browser_launcher_mock,
    spotify_launcher_mock,
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
        browser_launcher_mock.open.assert_not_called()
        spotify_launcher_mock.open.assert_not_called()


@pytest.mark.parametrize(
    ("action", "virtual_key"),
    [
        ("MEDIA_PLAY_PAUSE", 0xB3),
        ("MEDIA_PREVIOUS", 0xB1),
        ("MEDIA_NEXT", 0xB0),
        ("MEDIA_SEEK_BACK", 0x4A),
        ("MEDIA_SEEK_FORWARD", 0x4C),
        ("MEDIA_FULLSCREEN", 0x46),
        ("MEDIA_EXIT_FULLSCREEN", 0x1B),
    ],
)
def test_authenticated_media_control_uses_only_allowlisted_windows_keys(
    client,
    dispatcher,
    windows_key_event_mock,
    action,
    virtual_key,
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
            "message": "Comando enviado ao YouTube.",
            "data": {
                "intent": "MEDIA_CONTROL",
                "action": action,
                "platform": "YOUTUBE",
                "session": "WEB",
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


def test_media_control_requires_an_identified_active_session(
    client,
    dispatcher,
    media_session_detector_mock,
    windows_key_event_mock,
):
    media_session_detector_mock.detect.return_value = None

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "MEDIA_PLAY_PAUSE",
            "requestId": "media-session",
        })

        error = websocket.receive_json()

    assert error["code"] == "MEDIA_SESSION_NOT_FOUND"
    assert error["message"] == "Nenhuma plataforma de mídia ativa foi identificada."
    windows_key_event_mock.assert_not_called()


def test_media_control_rejects_action_unsupported_by_active_platform(
    client,
    dispatcher,
    media_session_detector_mock,
    windows_key_event_mock,
):
    media_session_detector_mock.detect.return_value = MediaSession(
        platform="SPOTIFY",
        kind="APP",
    )

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "MEDIA_FULLSCREEN",
            "requestId": "media-unsupported",
        })

        error = websocket.receive_json()

    assert error["code"] == "MEDIA_ACTION_UNSUPPORTED"
    assert error["message"] == "Fullscreen não é suportado no Spotify."
    windows_key_event_mock.assert_not_called()


def test_volume_get_requires_authentication(client, volume_adapter_mock):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "SYSTEM_VOLUME_GET",
            "requestId": "volume-1",
        })

        assert websocket.receive_json()["code"] == "UNAUTHORIZED"
        volume_adapter_mock.get_state.assert_not_awaited()


@pytest.mark.parametrize(
    ("message", "method", "expected_call", "expected_level", "expected_muted"),
    [
        ({"type": "SYSTEM_VOLUME_GET"}, "get_state", None, 42, False),
        (
            {"type": "SYSTEM_VOLUME_SET", "payload": {"level": 73}},
            "set_level",
            (73,),
            73,
            False,
        ),
        (
            {"type": "SYSTEM_VOLUME_DELTA", "payload": {"delta": 5}},
            "change_level",
            (5,),
            47,
            False,
        ),
        ({"type": "SYSTEM_MUTE_TOGGLE"}, "toggle_mute", None, 42, True),
    ],
)
def test_authenticated_volume_commands_return_real_adapter_state(
    client,
    dispatcher,
    volume_adapter_mock,
    message,
    method,
    expected_call,
    expected_level,
    expected_muted,
):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "requestId": "volume-1",
            **message,
        })

        result = websocket.receive_json()

        assert result["data"] == {
            "intent": "SYSTEM_VOLUME",
            "action": message["type"],
            "level": expected_level,
            "muted": expected_muted,
            "executed": True,
        }
        mocked_method = getattr(volume_adapter_mock, method)
        if expected_call is None:
            mocked_method.assert_awaited_once_with()
        else:
            mocked_method.assert_awaited_once_with(*expected_call)


@pytest.mark.parametrize(
    "message",
    [
        {"type": "SYSTEM_VOLUME_SET", "payload": {"level": -1}},
        {"type": "SYSTEM_VOLUME_SET", "payload": {"level": 101}},
        {"type": "SYSTEM_VOLUME_SET", "payload": {"level": True}},
        {"type": "SYSTEM_VOLUME_DELTA", "payload": {"delta": 10}},
        {"type": "SYSTEM_VOLUME_DELTA", "payload": {"delta": 0}},
        {"type": "SYSTEM_MUTE_TOGGLE", "payload": {"muted": True}},
    ],
)
def test_volume_commands_reject_out_of_allowlist_payloads(
    client,
    dispatcher,
    volume_adapter_mock,
    message,
):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "requestId": "volume-1",
            **message,
        })

        assert websocket.receive_json()["code"] == "INVALID_PAYLOAD"
        volume_adapter_mock.get_state.assert_not_awaited()
        volume_adapter_mock.set_level.assert_not_awaited()
        volume_adapter_mock.change_level.assert_not_awaited()
        volume_adapter_mock.toggle_mute.assert_not_awaited()


def test_volume_command_reports_native_failure(client, dispatcher, volume_adapter_mock):
    volume_adapter_mock.get_state.side_effect = WindowsVolumeError("unavailable")

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "SYSTEM_VOLUME_GET",
            "requestId": "volume-1",
        })

        error = websocket.receive_json()
        assert error["code"] == "SYSTEM_VOLUME_FAILED"
        assert error["message"] == "Controle de volume indisponível."


def test_pointer_control_requires_authentication(client, pointer_adapter_mock):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "POINTER_CLICK",
            "requestId": "pointer-1",
        })

        assert websocket.receive_json()["code"] == "UNAUTHORIZED"
        pointer_adapter_mock.click.assert_not_called()


@pytest.mark.parametrize(
    ("message", "method", "expected_call"),
    [
        ({"type": "POINTER_MOVE", "payload": {"dx": 12.5, "dy": -4}}, "move", (12.5, -4.0)),
        ({"type": "POINTER_CLICK"}, "click", ()),
        ({"type": "POINTER_DOUBLE_CLICK"}, "double_click", ()),
        ({"type": "POINTER_RIGHT_CLICK"}, "right_click", ()),
        ({"type": "POINTER_SCROLL", "payload": {"delta": -120}}, "scroll", (-120,)),
        ({"type": "POINTER_DOWN"}, "pointer_down", ()),
        ({"type": "POINTER_UP"}, "pointer_up", ()),
    ],
)
def test_authenticated_pointer_commands_use_only_fixed_adapter_methods(
    client,
    dispatcher,
    pointer_adapter_mock,
    message,
    method,
    expected_call,
):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "requestId": "pointer-1",
            **message,
        })

        result = websocket.receive_json()
        assert result == {
            "protocolVersion": 1,
            "type": "COMMAND_RESULT",
            "requestId": "pointer-1",
            "success": True,
            "message": "Comando do touchpad executado.",
            "data": {
                "intent": "POINTER_CONTROL",
                "action": message["type"],
                "executed": True,
            },
        }
        getattr(pointer_adapter_mock, method).assert_called_once_with(*expected_call)


@pytest.mark.parametrize(
    "message",
    [
        {"type": "POINTER_MOVE", "payload": {"dx": 161, "dy": 0}},
        {"type": "POINTER_MOVE", "payload": {"dx": 0, "dy": 0}},
        {"type": "POINTER_MOVE", "payload": {"dx": "12", "dy": 1}},
        {"type": "POINTER_SCROLL", "payload": {"delta": -240}},
        {"type": "POINTER_CLICK", "payload": {"button": "middle"}},
    ],
)
def test_pointer_commands_reject_extreme_or_arbitrary_payloads(
    client,
    dispatcher,
    pointer_adapter_mock,
    message,
):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "requestId": "pointer-1",
            **message,
        })

        assert websocket.receive_json()["code"] == "INVALID_PAYLOAD"
        pointer_adapter_mock.move.assert_not_called()


def test_pointer_move_is_rate_limited_per_connection(
    client,
    dispatcher,
    pointer_adapter_mock,
):
    dispatcher.pointer_rate_limiter = PointerRateLimiter(max_updates=1)

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        message = {
            "protocolVersion": 1,
            "type": "POINTER_MOVE",
            "requestId": "pointer-1",
            "payload": {"dx": 1, "dy": 1},
        }
        websocket.send_json(message)
        assert websocket.receive_json()["type"] == "COMMAND_RESULT"
        websocket.send_json({**message, "requestId": "pointer-2"})
        error = websocket.receive_json()

        assert error["code"] == "POINTER_RATE_LIMITED"
        assert pointer_adapter_mock.move.call_count == 1


def test_pointer_adapter_failure_is_reported(client, dispatcher, pointer_adapter_mock):
    pointer_adapter_mock.click.return_value = False

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "POINTER_CLICK",
            "requestId": "pointer-1",
        })

        assert websocket.receive_json()["code"] == "POINTER_CONTROL_FAILED"


def test_pointer_disconnect_releases_a_held_button(
    client,
    dispatcher,
    pointer_adapter_mock,
):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "POINTER_DOWN",
            "requestId": "pointer-1",
        })
        assert websocket.receive_json()["type"] == "COMMAND_RESULT"
        pointer_adapter_mock.pointer_up.reset_mock()

    pointer_adapter_mock.pointer_up.assert_called_once_with()


def test_keyboard_requires_authentication(client, keyboard_adapter_mock):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "KEYBOARD_TEXT",
            "requestId": "keyboard-1",
            "payload": {"text": "Olá"},
        })

        assert websocket.receive_json()["code"] == "UNAUTHORIZED"
        keyboard_adapter_mock.write_text.assert_not_called()


def test_authenticated_keyboard_text_is_sent_without_echoing_or_storing_it(
    client,
    dispatcher,
    keyboard_adapter_mock,
):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "KEYBOARD_TEXT",
            "requestId": "keyboard-1",
            "payload": {"text": "Olá, Fawkes!"},
        })

        result = websocket.receive_json()
        assert result == {
            "protocolVersion": 1,
            "type": "COMMAND_RESULT",
            "requestId": "keyboard-1",
            "success": True,
            "message": "Texto enviado.",
            "data": {
                "intent": "KEYBOARD_CONTROL",
                "action": "KEYBOARD_TEXT",
                "executed": True,
            },
        }
        assert "Olá" not in str(result)
        keyboard_adapter_mock.write_text.assert_called_once_with("Olá, Fawkes!")


@pytest.mark.parametrize(
    "key",
    [
        "ENTER",
        "BACKSPACE",
        "ESCAPE",
        "ARROW_UP",
        "ARROW_DOWN",
        "ARROW_LEFT",
        "ARROW_RIGHT",
        "TAB",
        "SPACE",
    ],
)
def test_authenticated_keyboard_uses_only_allowlisted_special_keys(
    client,
    dispatcher,
    keyboard_adapter_mock,
    key,
):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "KEYBOARD_KEY",
            "requestId": "keyboard-1",
            "payload": {"key": key},
        })

        result = websocket.receive_json()
        assert result["data"] == {
            "intent": "KEYBOARD_CONTROL",
            "action": "KEYBOARD_KEY",
            "executed": True,
        }
        keyboard_adapter_mock.press_key.assert_called_once_with(key)


@pytest.mark.parametrize(
    "message",
    [
        {"type": "KEYBOARD_TEXT", "payload": {"text": ""}},
        {"type": "KEYBOARD_TEXT", "payload": {"text": "   "}},
        {"type": "KEYBOARD_TEXT", "payload": {"text": "a" * 257}},
        {"type": "KEYBOARD_TEXT", "payload": {"text": "linha\nenter"}},
        {"type": "KEYBOARD_TEXT", "payload": {"text": 123}},
        {"type": "KEYBOARD_TEXT", "payload": {"text": "\ud800"}},
        {"type": "KEYBOARD_KEY", "payload": {"key": "CTRL_ALT_DELETE"}},
        {"type": "KEYBOARD_KEY", "payload": {"key": "A", "ctrl": True}},
    ],
)
def test_keyboard_rejects_unsafe_text_and_arbitrary_shortcuts(
    client,
    dispatcher,
    keyboard_adapter_mock,
    message,
):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "requestId": "keyboard-1",
            **message,
        })

        assert websocket.receive_json()["code"] == "INVALID_PAYLOAD"
        keyboard_adapter_mock.write_text.assert_not_called()
        keyboard_adapter_mock.press_key.assert_not_called()


def test_keyboard_adapter_failure_is_reported(client, dispatcher, keyboard_adapter_mock):
    keyboard_adapter_mock.write_text.return_value = False

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "KEYBOARD_TEXT",
            "requestId": "keyboard-1",
            "payload": {"text": "Olá"},
        })

        error = websocket.receive_json()
        assert error["code"] == "KEYBOARD_CONTROL_FAILED"
        assert error["message"] == "Teclado remoto indisponível."


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
    spotify_launcher_mock,
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
                "strategy": "SPOTIFY_APP",
            },
        }
        assert ready["state"] == "READY"
        spotify_launcher_mock.open.assert_called_once_with()


@pytest.mark.parametrize(
    ("command", "platform", "query", "strategy"),
    [
        ("abre YouTube Kanye West", "YOUTUBE", "Kanye West", "CHROME"),
        ("toca Runaway no Spotify", "SPOTIFY", "Runaway", "SPOTIFY_APP"),
    ],
)
def test_authenticated_media_search_executes_structured_intent(
    client,
    dispatcher,
    media_search_launcher_mock,
    command,
    platform,
    query,
    strategy,
):
    media_search_launcher_mock.search.return_value = BrowserLaunchResult(
        executed=True,
        strategy=strategy,
    )

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "TEXT_COMMAND",
            "requestId": "search-1",
            "payload": {"query": command},
        })

        assert websocket.receive_json()["state"] == "BUSY"
        result = websocket.receive_json()
        assert websocket.receive_json()["state"] == "READY"

    assert result == {
        "protocolVersion": 1,
        "type": "COMMAND_RESULT",
        "requestId": "search-1",
        "success": True,
        "message": f"Pesquisa aberta no {'YouTube' if platform == 'YOUTUBE' else 'Spotify'}.",
        "data": {
            "intent": "SEARCH_MEDIA",
            "platform": platform,
            "executed": True,
            "strategy": strategy,
        },
    }
    media_search_launcher_mock.search.assert_called_once_with(platform, query)


def test_media_search_failure_returns_error_without_false_success(
    client,
    dispatcher,
    media_search_launcher_mock,
):
    media_search_launcher_mock.search.return_value = BrowserLaunchResult(
        executed=False,
        error="CHROME_NOT_FOUND",
    )

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "TEXT_COMMAND",
            "requestId": "search-1",
            "payload": {"query": "pesquisa Fawkes no YouTube"},
        })

        assert websocket.receive_json()["state"] == "BUSY"
        error = websocket.receive_json()
        assert websocket.receive_json()["state"] == "READY"

    assert error["code"] == "MEDIA_SEARCH_FAILED"
    assert error["message"] == "Não foi possível abrir a pesquisa no YouTube."


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


def test_websocket_rejects_non_object_payloads(client):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)

        for raw in ("[]", "null", '"texto"', "123"):
            websocket.send_text(raw)
            data = websocket.receive_json()

            assert data["type"] == "ERROR"
            assert data["code"] == "INVALID_PAYLOAD"


def test_websocket_rejects_message_without_request_id(client):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "PLATFORM_SELECTED",
            "payload": {"platform": "NETFLIX"},
        })

        data = websocket.receive_json()

        assert data["type"] == "ERROR"
        assert data["requestId"] == "unknown"
        assert data["code"] == "INVALID_PAYLOAD"


def test_websocket_rejects_a_remote_page_origin(client):
    """CORS não cobre WebSocket: sem esta checagem uma página remota conecta."""
    with pytest.raises(WebSocketDisconnect) as rejection:
        with client.websocket_connect(
            "/ws",
            headers={"Origin": "https://evil.example"},
        ) as websocket:
            websocket.receive_json()

    assert rejection.value.code == WS_POLICY_VIOLATION


@pytest.mark.parametrize("origin", [
    "http://localhost:5173",
    "http://192.168.0.20:5173",
    "http://10.0.0.5:5173",
    "http://fawkes.local:5173",
])
def test_websocket_accepts_local_network_origins(client, origin):
    """O iPhone acessa pelo IP da LAN; isso não pode ser bloqueado."""
    with client.websocket_connect("/ws", headers={"Origin": origin}) as websocket:
        receive_auth_required(websocket)


def test_websocket_rejects_non_text_frames_without_dropping_the_session(client):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)

        websocket.send_bytes(b"\x00\x01\x02")

        assert websocket.receive_json()["code"] == "INVALID_PAYLOAD"
        # A sessão continua utilizável depois do frame inválido.
        websocket.send_text("{ quebrado ")
        assert websocket.receive_json()["code"] == "INVALID_JSON"


def test_held_pointer_button_is_released_when_the_session_ends(client, dispatcher, pointer_adapter_mock):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "POINTER_DOWN",
            "requestId": "down-1",
        })
        websocket.receive_json()
        assert len(dispatcher._held_pointer_buttons) == 1

    pointer_adapter_mock.pointer_up.assert_called()
    assert dispatcher._held_pointer_buttons == set()
    assert dispatcher._authenticated == {}
    assert dispatcher._connections == set()


def test_unexpected_handler_error_still_releases_the_pointer(
    client,
    dispatcher,
    pointer_adapter_mock,
    monkeypatch,
):
    """O cleanup precisa rodar em finally: um erro inesperado no meio da sessão
    não pode deixar o botão do mouse pressionado na máquina do usuário."""
    async def explode(*_args, **_kwargs):
        raise RuntimeError("falha inesperada no dispatcher")

    # O erro do servidor propaga na saída do contexto do cliente.
    with pytest.raises(RuntimeError):
        with client.websocket_connect("/ws") as websocket:
            receive_auth_required(websocket)
            pair(websocket, dispatcher)
            websocket.send_json({
                "protocolVersion": 1,
                "type": "POINTER_DOWN",
                "requestId": "down-1",
            })
            websocket.receive_json()

            monkeypatch.setattr(dispatcher, "dispatch", explode)
            websocket.send_json({
                "protocolVersion": 1,
                "type": "POINTER_UP",
                "requestId": "up-1",
            })
            websocket.receive_json()

    pointer_adapter_mock.pointer_up.assert_called()
    assert dispatcher._held_pointer_buttons == set()
    assert dispatcher._authenticated == {}
    assert dispatcher._connections == set()


def test_message_flood_is_rate_limited_per_connection(client, dispatcher):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)

        codes = []
        for index in range(Dispatcher.MAX_MESSAGES_PER_SECOND + 5):
            websocket.send_json({
                "protocolVersion": 1,
                "type": "PAIR_DEVICE",
                "requestId": f"flood-{index}",
                "payload": {"pin": "000000", "deviceName": "atacante"},
            })
            codes.append(websocket.receive_json()["code"])

    assert "RATE_LIMITED" in codes


def test_pairing_brute_force_is_locked_out_over_the_websocket(client, dispatcher):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        wrong_pin = "000000" if dispatcher.pairing_service.current_pin != "000000" else "111111"

        for index in range(PairingService.MAX_ATTEMPTS):
            websocket.send_json({
                "protocolVersion": 1,
                "type": "PAIR_DEVICE",
                "requestId": f"attack-{index}",
                "payload": {"pin": wrong_pin, "deviceName": "atacante"},
            })
            websocket.receive_json()

        # Mesmo o PIN correto é recusado enquanto o bloqueio estiver ativo.
        websocket.send_json({
            "protocolVersion": 1,
            "type": "PAIR_DEVICE",
            "requestId": "attack-final",
            "payload": {
                "pin": dispatcher.pairing_service.current_pin,
                "deviceName": "atacante",
            },
        })

        assert websocket.receive_json()["code"] == "TOO_MANY_ATTEMPTS"


def test_connection_limit_protects_the_server(client, dispatcher):
    opened = []
    try:
        for _ in range(Dispatcher.MAX_CONNECTIONS):
            context = client.websocket_connect("/ws")
            socket = context.__enter__()
            socket.receive_json()
            opened.append((context, socket))

        with pytest.raises(WebSocketDisconnect) as rejection:
            with client.websocket_connect("/ws") as extra:
                extra.receive_json()

        assert rejection.value.code == WS_TRY_AGAIN_LATER
    finally:
        for context, _ in opened:
            context.__exit__(None, None, None)


NAVIGATION_TO_KEY = [
    ("NAVIGATE_UP", "ARROW_UP"),
    ("NAVIGATE_DOWN", "ARROW_DOWN"),
    ("NAVIGATE_LEFT", "ARROW_LEFT"),
    ("NAVIGATE_RIGHT", "ARROW_RIGHT"),
    ("NAVIGATE_CONFIRM", "ENTER"),
    ("NAVIGATE_BACK", "ESCAPE"),
]


def test_navigation_requires_authentication(client, keyboard_adapter_mock):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "NAVIGATE_UP",
            "requestId": "nav-1",
        })

        assert websocket.receive_json()["code"] == "UNAUTHORIZED"

    keyboard_adapter_mock.press_key.assert_not_called()


@pytest.mark.parametrize(("action", "key"), NAVIGATION_TO_KEY)
def test_authenticated_navigation_uses_only_allowlisted_keys(
    client,
    dispatcher,
    keyboard_adapter_mock,
    action,
    key,
):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": action,
            "requestId": "nav-1",
        })

        result = websocket.receive_json()

        assert result["type"] == "COMMAND_RESULT"
        assert result["data"] == {
            "intent": "NAVIGATION",
            "action": action,
            "executed": True,
        }

    keyboard_adapter_mock.press_key.assert_called_once_with(key)


def test_navigation_rejects_home_and_arbitrary_payloads(client, dispatcher, keyboard_adapter_mock):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)

        # NAVIGATE_HOME ainda não existe: não pode ser aceito por engano.
        websocket.send_json({
            "protocolVersion": 1,
            "type": "NAVIGATE_HOME",
            "requestId": "nav-home",
        })
        assert websocket.receive_json()["code"] == "UNSUPPORTED_MESSAGE"

        # Sem payload livre: nada de tecla arbitrária pelo direcional.
        websocket.send_json({
            "protocolVersion": 1,
            "type": "NAVIGATE_UP",
            "requestId": "nav-2",
            "payload": {"key": "F4"},
        })
        assert websocket.receive_json()["code"] == "INVALID_PAYLOAD"

    keyboard_adapter_mock.press_key.assert_not_called()


def test_arrows_repeat_while_confirm_and_back_do_not(client, dispatcher, keyboard_adapter_mock):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)

        # Segurar a seta: repetição é esperada e permitida.
        for index in range(8):
            websocket.send_json({
                "protocolVersion": 1,
                "type": "NAVIGATE_DOWN",
                "requestId": f"down-{index}",
            })
            assert websocket.receive_json()["type"] == "COMMAND_RESULT"

        # Confirmar repetido entra em vários itens: precisa ser barrado.
        codes = []
        for index in range(8):
            websocket.send_json({
                "protocolVersion": 1,
                "type": "NAVIGATE_CONFIRM",
                "requestId": f"ok-{index}",
            })
            message = websocket.receive_json()
            codes.append(message.get("code") or message["type"])

    assert "NAVIGATION_RATE_LIMITED" in codes


def test_navigation_flood_is_rate_limited_without_consuming_the_keyboard_quota(
    client,
    dispatcher,
    keyboard_adapter_mock,
):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)

        codes = []
        for index in range(Dispatcher.MAX_NAVIGATION_PER_SECOND + 5):
            websocket.send_json({
                "protocolVersion": 1,
                "type": "NAVIGATE_UP",
                "requestId": f"nav-{index}",
            })
            message = websocket.receive_json()
            codes.append(message.get("code") or message["type"])

        assert "NAVIGATION_RATE_LIMITED" in codes

        # O teclado remoto continua utilizável: os limites são independentes.
        websocket.send_json({
            "protocolVersion": 1,
            "type": "KEYBOARD_KEY",
            "requestId": "kb-1",
            "payload": {"key": "ENTER"},
        })
        assert websocket.receive_json()["type"] == "COMMAND_RESULT"


def test_navigation_reports_adapter_failure(client, dispatcher, keyboard_adapter_mock):
    keyboard_adapter_mock.press_key.return_value = False

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "NAVIGATE_UP",
            "requestId": "nav-1",
        })

        assert websocket.receive_json()["code"] == "NAVIGATION_FAILED"


def test_authenticated_youtube_link_is_opened_only_in_chrome(
    client,
    dispatcher,
    browser_launcher_mock,
):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "TEXT_COMMAND",
            "requestId": "link-1",
            "payload": {"query": "https://youtu.be/dQw4w9WgXcQ"},
        })

        assert websocket.receive_json()["state"] == "BUSY"
        result = websocket.receive_json()
        assert websocket.receive_json()["state"] == "READY"

        assert result["type"] == "COMMAND_RESULT"
        assert result["data"] == {
            "intent": "OPEN_ALLOWED_MEDIA_LINK",
            "platform": "YOUTUBE",
            "executed": True,
            "strategy": "CHROME",
        }

    # A URL aberta é a canônica montada no backend, não a enviada pelo cliente.
    browser_launcher_mock.open.assert_called_once_with(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    )


@pytest.mark.parametrize("query", [
    "https://evil.example/watch?v=dQw4w9WgXcQ",
    "https://www.youtube.com.evil.example/watch?v=dQw4w9WgXcQ",
    "javascript:alert(1)",
    "file:///C:/Windows/System32/cmd.exe",
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ&redirect=https://evil.example",
])
def test_unsafe_links_never_reach_the_browser(client, dispatcher, browser_launcher_mock, query):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "TEXT_COMMAND",
            "requestId": "link-1",
            "payload": {"query": query},
        })

        websocket.receive_json()
        error = websocket.receive_json()

        assert error["type"] == "ERROR"
        assert error["code"] == "UNKNOWN_COMMAND"

    browser_launcher_mock.open.assert_not_called()


def test_media_link_failure_is_reported_without_false_success(
    client,
    dispatcher,
    browser_launcher_mock,
):
    browser_launcher_mock.open.return_value = BrowserLaunchResult(
        executed=False,
        error="CHROME_NOT_FOUND",
    )

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "TEXT_COMMAND",
            "requestId": "link-1",
            "payload": {"query": "https://youtu.be/dQw4w9WgXcQ"},
        })

        websocket.receive_json()
        error = websocket.receive_json()

        assert error["type"] == "ERROR"
        assert error["code"] == "MEDIA_LINK_FAILED"
        assert "Chrome" in error["message"]


def test_reset_input_state_releases_keys_and_the_mouse(
    client,
    dispatcher,
    keyboard_adapter_mock,
    pointer_adapter_mock,
):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "POINTER_DOWN",
            "requestId": "down-1",
        })
        websocket.receive_json()

        websocket.send_json({
            "protocolVersion": 1,
            "type": "RESET_INPUT_STATE",
            "requestId": "reset-1",
        })
        result = websocket.receive_json()

        assert result["type"] == "COMMAND_RESULT"
        assert result["data"]["action"] == "RESET_INPUT_STATE"
        keyboard_adapter_mock.release_all.assert_called()
        pointer_adapter_mock.pointer_up.assert_called()
        assert dispatcher._held_pointer_buttons == set()


def test_reset_input_state_is_never_rate_limited(client, dispatcher, keyboard_adapter_mock):
    """É a saída de emergência: barrá-la deixaria a tecla presa."""
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)

        for index in range(Dispatcher.MAX_NAVIGATION_PER_SECOND + 10):
            websocket.send_json({
                "protocolVersion": 1,
                "type": "RESET_INPUT_STATE",
                "requestId": f"reset-{index}",
            })
            assert websocket.receive_json()["type"] == "COMMAND_RESULT"


def test_reset_input_state_requires_authentication(client, keyboard_adapter_mock):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "RESET_INPUT_STATE",
            "requestId": "reset-1",
        })

        assert websocket.receive_json()["code"] == "UNAUTHORIZED"
        # Verificado ainda dentro da conexão: sair do contexto dispara o
        # release defensivo do disconnect, que é esperado.
        keyboard_adapter_mock.release_all.assert_not_called()


def test_disconnecting_releases_the_keyboard(client, dispatcher, keyboard_adapter_mock):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)

    # Cair a conexão no meio de um comando não pode deixar seta repetindo.
    keyboard_adapter_mock.release_all.assert_called()
