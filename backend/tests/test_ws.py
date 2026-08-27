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
from app.windows.app_volume import (
    AppVolumeState,
    AppVolumeUnavailable,
    WindowsAppVolumeAdapter,
)
from app.protocol import dispatcher as dispatcher_module
from app.windows.focus import DesktopWindow, WindowFocuser
from app.input.pointer import PointerRateLimiter, WindowsPointerAdapter
from app.input.keyboard import WindowsKeyboardAdapter
from app.platforms.browser import BrowserLaunchResult, BrowserLauncher
from app.platforms.launcher import PlatformLauncher
from app.platforms.spotify import SpotifyLauncher
from app.platforms.search import MediaSearchLauncher
from app.intelligence.intents import LocalSearchMediaIntent
from app.intelligence.service import IntentFallbackService


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
def app_volume_adapter_mock():
    """Sem sessão local por padrão: exercita o fallback para o volume global."""
    adapter = Mock(spec=WindowsAppVolumeAdapter)
    adapter.get_state.side_effect = AppVolumeUnavailable("sem sessão")
    adapter.set_level.side_effect = AppVolumeUnavailable("sem sessão")
    adapter.change_level.side_effect = AppVolumeUnavailable("sem sessão")
    adapter.toggle_mute.side_effect = AppVolumeUnavailable("sem sessão")
    return adapter


@pytest.fixture
def keyboard_adapter_mock():
    adapter = Mock(spec=WindowsKeyboardAdapter)
    adapter.write_text.return_value = True
    adapter.press_key.return_value = True
    return adapter


@pytest.fixture
def window_focuser_mock():
    """Foco resolvido, sem tocar nas janelas reais da máquina.

    O padrão varre o desktop de verdade, então sem este mock o resultado do
    teste passaria a depender do que estiver aberto na hora.
    """
    focuser = Mock(spec=WindowFocuser)
    focuser.focus_platform.return_value = True
    # Sem janela localizada por padrão: assim a tela cheia cai no atalho de
    # teclado, e cada teste que quer o caminho do duplo clique monta a janela
    # explicitamente.
    focuser.find.return_value = None
    # E o MESMO para `media_window`, que faltava.
    #
    # Sem esta linha ela devolvia um `Mock`, que não é `None` — então o socorro
    # pela janela entrava com um título que não é texto, e
    # `limpar_titulo_de_janela` estourava com "'Mock' object is not iterable".
    # A leitura inteira morria, o cartão nunca era enviado, e o celular recebia
    # só o batimento.
    #
    # Passava NESTA máquina e quebrava no CI, porque o socorro só entra quando
    # a SMTC não responde: aqui o `winsdk` está instalado e a leitura vinha por
    # ele, então este caminho nunca era exercitado. No Linux não há `winsdk`, e
    # 141 testes caíram de uma vez com `assert 'HEARTBEAT' == 'NOW_PLAYING'`.
    focuser.media_window.return_value = None
    return focuser


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
    app_volume_adapter_mock,
    window_focuser_mock,
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
        app_volume_adapter=app_volume_adapter_mock,
        window_focuser=window_focuser_mock,
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
    # O cartão do que está tocando chega logo depois de autenticar, para o
    # celular não ficar com a tela vazia até a próxima mudança. Consumir aqui
    # deixa os testes falando só do que cada um quer testar.
    tocando = websocket.receive_json()
    assert tocando["type"] == "NOW_PLAYING"
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
                "focused": True,
                "executed": True,
            },
        }
        # A tecla é a da lista, pressionada e solta — e agora com o scan code
        # e a flag de tecla ESTENDIDA que fazem o Windows entregá-la como o
        # teclado de verdade entregaria. Sem a flag, seta-esquerda chega como o
        # 4 do numérico e o player web ignora; foi o que quebrou avançar e
        # voltar 10s. Ver `app/input/teclas.py`.
        from app.input.teclas import flags_de, scan_code_de

        scan = scan_code_de(virtual_key)
        assert windows_key_event_mock.call_args_list == [
            call(virtual_key, scan, flags_de(virtual_key), 0),
            call(virtual_key, scan, flags_de(virtual_key, soltando=True), 0),
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
    # Sem sessão de mídia não é falha: é o estado de quem ainda não começou a
    # assistir. A resposta precisa dizer o que fazer, não só constatar.
    assert error["message"] == "Nada tocando agora. Abra uma plataforma para começar."
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
            # Sem sessão local: caiu para o volume do Windows, e isso aparece.
            "scope": "GLOBAL",
            "target": None,
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


def test_deterministic_media_text_uses_the_existing_media_handler(
    client,
    dispatcher,
    windows_key_event_mock,
):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "TEXT_COMMAND",
            "requestId": "text-media",
            "payload": {"query": "play"},
        })

        assert websocket.receive_json()["state"] == "BUSY"
        result = websocket.receive_json()
        assert websocket.receive_json()["state"] == "READY"

    assert result["data"]["intent"] == "MEDIA_CONTROL"
    assert result["data"]["action"] == "MEDIA_PLAY_PAUSE"
    assert windows_key_event_mock.call_count == 2


def test_deterministic_volume_text_uses_the_existing_volume_handler(
    client,
    dispatcher,
    volume_adapter_mock,
):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "TEXT_COMMAND",
            "requestId": "text-volume",
            "payload": {"query": "volume 42"},
        })

        assert websocket.receive_json()["state"] == "BUSY"
        result = websocket.receive_json()
        assert websocket.receive_json()["state"] == "READY"

    assert result["data"]["intent"] == "SYSTEM_VOLUME"
    assert result["data"]["action"] == "SYSTEM_VOLUME_SET"
    volume_adapter_mock.set_level.assert_awaited_once_with(42)


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


def test_known_text_command_bypasses_the_local_resolver(client, dispatcher):
    resolver = AsyncMock()
    dispatcher.intent_service = IntentFallbackService(resolver)

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "TEXT_COMMAND",
            "requestId": "known-bypass",
            "payload": {"query": "play"},
        })
        assert websocket.receive_json()["state"] == "BUSY"
        assert websocket.receive_json()["type"] == "COMMAND_RESULT"
        assert websocket.receive_json()["state"] == "READY"

    resolver.resolve.assert_not_awaited()


def test_unknown_text_may_resolve_once_through_local_intent_and_existing_adapter(
    client,
    dispatcher,
    media_search_launcher_mock,
):
    resolver = AsyncMock()
    resolver.resolve.return_value = LocalSearchMediaIntent(
        intent="SEARCH_MEDIA",
        platform="YOUTUBE",
        query="Interestelar trailer",
    )
    dispatcher.intent_service = IntentFallbackService(resolver)

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        credentials = pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "TEXT_COMMAND",
            "requestId": "seed-context",
            "payload": {"query": "abre YouTube"},
        })
        assert websocket.receive_json()["state"] == "BUSY"
        assert websocket.receive_json()["type"] == "COMMAND_RESULT"
        assert websocket.receive_json()["state"] == "READY"
        websocket.send_json({
            "protocolVersion": 1,
            "type": "TEXT_COMMAND",
            "requestId": "unknown-local",
            "payload": {"query": "escolhe um filme"},
        })
        assert websocket.receive_json()["state"] == "BUSY"
        result = websocket.receive_json()
        assert websocket.receive_json()["state"] == "READY"

    assert result["data"]["intent"] == "SEARCH_MEDIA"
    resolver.resolve.assert_awaited_once()
    assert resolver.resolve.await_args.args[0] == "escolhe um filme"
    media_search_launcher_mock.search.assert_called_once_with("YOUTUBE", "Interestelar trailer")
    context = dispatcher.intent_service.context_store.get(credentials["deviceId"])
    assert context.query == "Interestelar trailer"


def test_invalid_local_output_preserves_unknown_command_fallback(client, dispatcher):
    resolver = AsyncMock()
    resolver.resolve.return_value = None
    dispatcher.intent_service = IntentFallbackService(resolver)

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "TEXT_COMMAND",
            "requestId": "unknown-safe",
            "payload": {"query": "escolhe um filme"},
        })
        assert websocket.receive_json()["state"] == "BUSY"
        error = websocket.receive_json()
        assert websocket.receive_json()["state"] == "READY"

    assert error["code"] == "UNKNOWN_COMMAND"
    resolver.resolve.assert_awaited_once()


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


def test_disconnecting_releases_only_what_got_stuck(
    client,
    dispatcher,
    keyboard_adapter_mock,
):
    """Cair a conexão não pode deixar seta repetindo — nem mandar Escape.

    O celular desconecta o tempo todo: tela apagada, troca de app, oscilação
    de rede. Soltar a lista inteira de teclas em cada uma dessas mandava um
    keyup de Escape para a janela em foco, e o Escape tira o navegador da tela
    cheia. Na prática, o filme saía de tela cheia sozinho quando o usuário
    guardava o celular.
    """
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)

    keyboard_adapter_mock.release_stuck.assert_called()
    keyboard_adapter_mock.release_all.assert_not_called()


def test_volume_prefers_the_active_app_and_says_so(
    client,
    dispatcher,
    app_volume_adapter_mock,
    volume_adapter_mock,
):
    app_volume_adapter_mock.change_level.side_effect = None
    app_volume_adapter_mock.change_level.return_value = AppVolumeState(
        level=55,
        muted=False,
        process="spotify.exe",
    )
    dispatcher.media_session_detector.detect.return_value = MediaSession(
        platform="SPOTIFY",
        kind="APP",
    )

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "SYSTEM_VOLUME_DELTA",
            "requestId": "volume-1",
            "payload": {"delta": 5},
        })

        result = websocket.receive_json()

        assert result["data"]["scope"] == "LOCAL"
        assert result["data"]["target"] == "Spotify"
        assert result["data"]["level"] == 55
        assert result["message"] == "Volume do Spotify: 55%."

    # O volume do Windows não foi tocado.
    volume_adapter_mock.change_level.assert_not_called()


def test_volume_falls_back_to_windows_without_hiding_it(
    client,
    dispatcher,
    app_volume_adapter_mock,
    volume_adapter_mock,
):
    # Sem sessão de áudio do aplicativo: precisa cair no global e avisar.
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "SYSTEM_VOLUME_DELTA",
            "requestId": "volume-1",
            "payload": {"delta": 5},
        })

        result = websocket.receive_json()

        assert result["data"]["scope"] == "GLOBAL"
        assert "geral" in result["message"]
        assert result["message"] == "Volume geral do Windows: 47%."

    volume_adapter_mock.change_level.assert_called_once_with(5)


def test_volume_falls_back_when_no_media_session_is_identified(
    client,
    dispatcher,
    app_volume_adapter_mock,
    volume_adapter_mock,
):
    dispatcher.media_session_detector.detect.return_value = None

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "SYSTEM_VOLUME_GET",
            "requestId": "volume-1",
        })

        result = websocket.receive_json()

        assert result["data"]["scope"] == "GLOBAL"
    app_volume_adapter_mock.get_state.assert_not_called()
    volume_adapter_mock.get_state.assert_called_once()


def test_local_mute_reports_the_app_it_muted(
    client,
    dispatcher,
    app_volume_adapter_mock,
):
    app_volume_adapter_mock.toggle_mute.side_effect = None
    app_volume_adapter_mock.toggle_mute.return_value = AppVolumeState(
        level=40,
        muted=True,
        process="chrome.exe",
    )

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "SYSTEM_MUTE_TOGGLE",
            "requestId": "mute-1",
        })

        result = websocket.receive_json()

        assert result["data"]["scope"] == "LOCAL"
        assert result["data"]["target"] == "Chrome"
        assert result["message"] == "Volume do Chrome: mudo ativado, 40%."


def ask_where_to_search(websocket, dispatcher, query: str, request_id: str) -> dict:
    websocket.send_json({
        "protocolVersion": 1,
        "type": "TEXT_COMMAND",
        "requestId": request_id,
        "payload": {"query": query},
    })
    websocket.receive_json()  # BUSY
    # Pula o que chega sozinho: o cartão de "tocando agora" é empurrado a cada
    # segundo, e uma busca que consulta o catálogo dá tempo de sobra para ele
    # cair no meio. O teste é sobre a resposta ao comando, não sobre a ordem em
    # que as duas coisas chegam.
    for _ in range(6):
        mensagem = websocket.receive_json()
        if mensagem["type"] not in ("NOW_PLAYING", "HEARTBEAT"):
            return mensagem
    raise AssertionError("só chegou mensagem espontânea")


def test_the_choice_offers_max_and_disney_as_open_only(client, dispatcher):
    """Um título que só existe no Max não tinha caminho nenhum pelo controle.

    As duas não têm URL de busca estável, então continuam separadas das que
    recebem a consulta — mas some da lista era pior: dava a impressão de que a
    plataforma não era suportada.
    """
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)

        message = ask_where_to_search(websocket, dispatcher, "Harry Potter", "needs-1")

        assert message["type"] == "NEEDS_PLATFORM"
        assert message["query"] == "Harry Potter"
        assert message["openOnlyPlatforms"] == ["MAX", "DISNEY_PLUS"]
        # Nenhuma das duas pode aparecer como busca direta: prometeria levar a
        # consulta para uma tela que a descarta.
        assert "MAX" not in message["suggestedPlatforms"]
        assert "DISNEY_PLUS" not in message["suggestedPlatforms"]


def test_naming_max_still_asks_where_to_search_and_offers_max(client, dispatcher):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)

        message = ask_where_to_search(
            websocket, dispatcher, "coloca Harry Potter no Max", "needs-2",
        )

        assert message["type"] == "NEEDS_PLATFORM"
        assert message["query"] == "Harry Potter"
        assert "MAX" in message["openOnlyPlatforms"]


def test_a_music_request_does_not_offer_video_only_platforms(client, dispatcher):
    """"toca alguma coisa" no Max não faz sentido; oferecer só polui a escolha."""
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)

        message = ask_where_to_search(websocket, dispatcher, "toca Runaway", "needs-3")

        assert message["type"] == "NEEDS_PLATFORM"
        assert message["openOnlyPlatforms"] == []
        assert message["suggestedPlatforms"][0] == "SPOTIFY"


class CatalogoDeDoisResultados:
    """O catálogo quando o nome serve para duas obras diferentes."""

    enabled = True

    async def buscar_para_escolha(self, query: str, limite: int | None = None):
        from app.catalog.tmdb import TitleAvailability

        return [
            TitleAvailability("O Justiceiro", 2004, None, ["MAX"], "MOVIE"),
            TitleAvailability("Marvel - O Justiceiro", 2017, None, ["DISNEY_PLUS"], "TV"),
        ]


def test_the_choice_carries_the_other_reading_of_the_same_name(client, dispatcher):
    """Escolher sozinho entre o filme e a série erra metade das vezes.

    Medido no catálogo real: "o justiceiro" é um filme de 2004 no Max e a série
    da Marvel de 2017 no Disney+. Quem estava assistindo à série no Disney+
    recebia o filme, sem nenhuma forma de corrigir pela tela.
    """
    dispatcher.catalog = CatalogoDeDoisResultados()

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)

        message = ask_where_to_search(websocket, dispatcher, "o justiceiro", "needs-4")

        assert message["availability"]["title"] == "O Justiceiro"
        assert message["availability"]["kind"] == "MOVIE"
        assert message["availabilityAlternative"]["title"] == "Marvel - O Justiceiro"
        assert message["availabilityAlternative"]["kind"] == "TV"


def test_the_choice_carries_every_reading_not_just_two(client, dispatcher):
    """Dois slots era o formato de "adivinhar a obra e oferecer a alternativa".

    Para BUSCAR é pouco, e o quanto ficou medido em 25/08/2026: "capitão
    américa" tinha os quatro filmes da Marvel entre os candidatos e a tela
    mostrava o de 1990 — que não está em serviço nenhum — mais um.

    Os dois campos antigos continuam preenchidos com os dois primeiros: um
    cliente que não conhece a lista segue funcionando.
    """
    class CatalogoDeMuitos:
        enabled = True

        async def buscar_para_escolha(self, query: str, limite: int | None = None):
            from app.catalog.tmdb import TitleAvailability

            return [
                TitleAvailability(f"Opção {i}", 2000 + i, None, ["MAX"], "MOVIE")
                for i in range(1, 7)
            ]

    dispatcher.catalog = CatalogoDeMuitos()

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)

        message = ask_where_to_search(websocket, dispatcher, "opcao", "needs-5")

        assert len(message["availabilityOptions"]) == 6
        # E os dois campos antigos são os dois primeiros da lista.
        assert message["availability"]["title"] == "Opção 1"
        assert message["availabilityAlternative"]["title"] == "Opção 2"
        assert message["availabilityOptions"][0]["title"] == "Opção 1"


def test_a_music_request_never_asks_the_movie_catalog(client, dispatcher):
    dispatcher.catalog = CatalogoDeDoisResultados()

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)

        message = ask_where_to_search(websocket, dispatcher, "toca Runaway", "needs-5")

        assert message["availability"] is None
        assert message["availabilityAlternative"] is None


def send_media(websocket, dispatcher, action: str = "MEDIA_FULLSCREEN") -> dict:
    websocket.send_json({
        "protocolVersion": 1,
        "type": action,
        "requestId": "media-focus",
    })
    return websocket.receive_json()


def test_the_platform_window_is_focused_before_the_key_is_sent(
    client,
    dispatcher,
    window_focuser_mock,
    windows_key_event_mock,
):
    """A tecla vai para a janela em primeiro plano, seja ela qual for.

    Sem trazer a plataforma para frente, "tela cheia" digitava um "f" no editor
    de código e "+10s" mandava seta para o Explorer — e a resposta dizia
    "comando enviado" nos dois casos.
    """
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)

        result = send_media(websocket, dispatcher)

        window_focuser_mock.focus_platform.assert_called_once_with("YOUTUBE")
        assert result["data"]["focused"] is True
        assert windows_key_event_mock.called


def test_the_answer_stops_claiming_success_when_the_window_could_not_be_focused(
    client,
    dispatcher,
    window_focuser_mock,
):
    window_focuser_mock.focus_platform.return_value = False

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)

        result = send_media(websocket, dispatcher)

        assert result["data"]["focused"] is False
        assert "deixe a janela dele visível" in result["message"]


def test_a_failed_focus_still_sends_the_key(
    client,
    dispatcher,
    window_focuser_mock,
    windows_key_event_mock,
):
    """A janela pode já estar na frente sem que o foco precise mudar; desistir
    do envio transformaria um caso que funciona num erro."""
    window_focuser_mock.focus_platform.return_value = False

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        send_media(websocket, dispatcher)

    assert windows_key_event_mock.called


def test_fullscreen_double_clicks_the_video_instead_of_pressing_f(
    client,
    dispatcher,
    window_focuser_mock,
    pointer_adapter_mock,
    windows_key_event_mock,
):
    """O atalho F é de cada site e nenhum aplica igual.

    Medido: no Max, com a janela em foco, o F não fazia absolutamente nada. O
    duplo clique sobre o vídeo é o gesto que todo player web implementa, e foi
    o que funcionou no uso real.
    """
    janela = DesktopWindow(handle=42, process="chrome.exe", title="Filme - Netflix")
    window_focuser_mock.find.return_value = janela
    window_focuser_mock.center_of.return_value = (800, 450)

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        result = send_media(websocket, dispatcher, "MEDIA_FULLSCREEN")

    assert result["type"] == "COMMAND_RESULT"
    pointer_adapter_mock.move_to.assert_called_once_with(800, 450)
    pointer_adapter_mock.double_click.assert_called_once()
    windows_key_event_mock.assert_not_called()


def test_fullscreen_falls_back_to_the_key_when_the_window_is_not_found(
    client,
    dispatcher,
    window_focuser_mock,
    pointer_adapter_mock,
    windows_key_event_mock,
):
    """Sem janela localizada não há onde clicar; tentar a tecla é melhor do que
    responder que o comando falhou."""
    window_focuser_mock.find.return_value = None

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        send_media(websocket, dispatcher, "MEDIA_FULLSCREEN")

    pointer_adapter_mock.double_click.assert_not_called()
    assert windows_key_event_mock.called


def test_leaving_fullscreen_still_uses_escape(
    client,
    dispatcher,
    window_focuser_mock,
    pointer_adapter_mock,
    windows_key_event_mock,
):
    """Escape é do navegador, não do site: sai da tela cheia em qualquer um.
    Um segundo duplo clique dependeria do player tratar o toggle igual."""
    window_focuser_mock.find.return_value = DesktopWindow(
        handle=42, process="chrome.exe", title="Filme - Netflix",
    )

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        send_media(websocket, dispatcher, "MEDIA_EXIT_FULLSCREEN")

    pointer_adapter_mock.double_click.assert_not_called()
    assert windows_key_event_mock.call_args_list[0].args[0] == 0x1B


def test_spotify_never_gets_a_click_in_the_middle_of_its_window(
    client,
    dispatcher,
    window_focuser_mock,
    pointer_adapter_mock,
):
    """O Spotify não tem tela cheia de vídeo; um clique no meio da janela
    acertaria a lista de músicas."""
    dispatcher.media_session_detector.detect.return_value = MediaSession(
        platform="SPOTIFY", kind="APP",
    )

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        result = send_media(websocket, dispatcher, "MEDIA_FULLSCREEN")

    assert result["type"] == "ERROR"
    assert result["code"] == "MEDIA_ACTION_UNSUPPORTED"
    pointer_adapter_mock.double_click.assert_not_called()


def test_the_card_arrives_right_after_authenticating(client, dispatcher):
    """Sem isto o cartão só apareceria na próxima mudança — e com o filme
    tocando parado, o celular ficaria sem nada até alguém apertar pausa."""
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "PAIR_DEVICE",
            "requestId": "pair-card",
            "payload": {
                "pin": dispatcher.pairing_service.current_pin,
                "deviceName": "iPhone",
            },
        })
        websocket.receive_json()  # PAIR_RESULT
        websocket.receive_json()  # READY
        cartao = websocket.receive_json()

    assert cartao["type"] == "NOW_PLAYING"
    assert "session" in cartao


def test_nothing_playing_is_a_state_that_gets_sent(client, dispatcher, monkeypatch):
    """"Nada tocando" precisa chegar: sem ele o cartão anterior ficaria
    congelado na tela depois de o filme acabar."""
    async def sem_midia():
        return None

    monkeypatch.setattr(dispatcher.now_playing_reader, "read", sem_midia)

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "PAIR_DEVICE",
            "requestId": "pair-vazio",
            "payload": {
                "pin": dispatcher.pairing_service.current_pin,
                "deviceName": "iPhone",
            },
        })
        websocket.receive_json()
        websocket.receive_json()
        cartao = websocket.receive_json()

    assert cartao == {"protocolVersion": 1, "type": "NOW_PLAYING", "session": None}


def test_the_thumbnail_needs_the_same_token_as_everything_else(client, dispatcher):
    dispatcher.thumbnails["capa-1"] = b"\x89PNG\r\n\x1a\nfake"

    sem_token = client.get("/now-playing/thumbnail/capa-1")
    errado = client.get(
        "/now-playing/thumbnail/capa-1",
        headers={"X-Device-Id": "x", "X-Device-Token": "y"},
    )

    assert sem_token.status_code == 401
    assert errado.status_code == 401


def test_an_unknown_thumbnail_is_a_clean_404(client, dispatcher):
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        resultado = pair(websocket, dispatcher)

    resposta = client.get(
        "/now-playing/thumbnail/nao-existe",
        headers={
            "X-Device-Id": resultado["deviceId"],
            "X-Device-Token": resultado["token"],
        },
    )

    assert resposta.status_code == 404


def test_the_server_proves_the_connection_is_alive(client, dispatcher, monkeypatch):
    """O ping do protocolo WebSocket é respondido pelo navegador sem passar
    pelo JavaScript, então a página não tem como saber que ele parou. Quando o
    Wi-Fi troca de rede, a conexão fica meio aberta: o `onclose` nunca dispara
    e o controle segue mostrando "conectado" com todo comando falhando calado.
    """
    from app.protocol import dispatcher as modulo

    # Encurta o relógio para o teste não esperar dez segundos de verdade.
    monkeypatch.setattr(modulo, "NOW_PLAYING_INTERVAL_SECONDS", 0.02)
    monkeypatch.setattr(modulo, "HEARTBEAT_INTERVAL_SECONDS", 0.04)

    async def sem_midia():
        return None

    monkeypatch.setattr(dispatcher.now_playing_reader, "read", sem_midia)

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)

        recebidos = [websocket.receive_json()["type"] for _ in range(3)]

    assert "HEARTBEAT" in recebidos


def test_the_heartbeat_carries_nothing_but_its_own_type(client, dispatcher):
    """Ele existe só para provar que a conexão está viva; qualquer campo a
    mais viraria estado que o celular precisaria interpretar."""
    from app.schemas.ws import HeartbeatMessage

    assert HeartbeatMessage().model_dump() == {
        "protocolVersion": 1,
        "type": "HEARTBEAT",
    }


def test_the_position_alone_does_not_trigger_a_new_message(dispatcher):
    """O laço dizia mandar "só quando muda", mas a posição muda a cada segundo
    — na prática era um envio por segundo por dispositivo, exatamente o que a
    regra queria evitar. Quem conta os segundos é o celular."""
    from app.protocol.dispatcher import POSITION_RESYNC_SECONDS

    def mensagem(posicao: float, tocando: bool = True) -> dict:
        return {
            "protocolVersion": 1,
            "type": "NOW_PLAYING",
            "session": {
                "title": "Duna", "artist": None, "app": "Chrome", "platform": None,
                "playing": tocando, "positionSeconds": posicao,
                "durationSeconds": 600.0, "thumbnailId": None,
            },
        }

    dispatcher._last_now_playing = mensagem(10.0)

    assert dispatcher._vale_enviar(mensagem(11.0), 1.0) is False
    assert dispatcher._vale_enviar(mensagem(12.0), 2.0) is False
    # Pausar muda algo de verdade e precisa chegar na hora.
    assert dispatcher._vale_enviar(mensagem(12.0, tocando=False), 2.0) is True
    # E a ressincronização periódica evita a barra derivar numa sessão longa.
    assert dispatcher._vale_enviar(mensagem(30.0), POSITION_RESYNC_SECONDS) is True


def test_a_title_change_is_sent_immediately(dispatcher):
    base = {
        "protocolVersion": 1, "type": "NOW_PLAYING",
        "session": {
            "title": "Duna", "artist": None, "app": "Chrome", "platform": None,
            "playing": True, "positionSeconds": 10.0,
            "durationSeconds": 600.0, "thumbnailId": None,
        },
    }
    dispatcher._last_now_playing = base
    outro = {**base, "session": {**base["session"], "title": "Interestelar"}}

    assert dispatcher._vale_enviar(outro, 0.5) is True


def test_going_from_playing_to_nothing_is_sent_immediately(dispatcher):
    """Sem isso o cartão do filme anterior ficaria congelado na tela."""
    dispatcher._last_now_playing = {
        "protocolVersion": 1, "type": "NOW_PLAYING",
        "session": {
            "title": "Duna", "artist": None, "app": "Chrome", "platform": None,
            "playing": True, "positionSeconds": 10.0,
            "durationSeconds": 600.0, "thumbnailId": None,
        },
    }
    vazio = {"protocolVersion": 1, "type": "NOW_PLAYING", "session": None}

    assert dispatcher._vale_enviar(vazio, 0.5) is True


def test_choosing_max_from_a_query_lands_on_its_search_screen(
    client,
    dispatcher,
    browser_launcher_mock,
):
    """Abrir a home obrigava a achar e clicar na lupa antes de digitar. Medido:
    `play.max.com/search` abre direto na tela de busca para quem está logado."""
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "PLATFORM_SELECTED",
            "requestId": "busca-max",
            "payload": {"platform": "MAX", "openSearch": True},
        })
        websocket.receive_json()

    browser_launcher_mock.open.assert_called_once_with("https://play.max.com/search")


def test_just_opening_max_still_lands_on_the_home(
    client,
    dispatcher,
    browser_launcher_mock,
):
    """"abre o Max" é outro pedido: quem só quer a plataforma não quer cair
    numa tela de busca vazia."""
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "PLATFORM_SELECTED",
            "requestId": "abre-max",
            "payload": {"platform": "MAX"},
        })
        websocket.receive_json()

    browser_launcher_mock.open.assert_called_once_with("https://www.max.com")


def test_a_platform_without_a_search_page_falls_back_to_its_home(
    client,
    dispatcher,
    browser_launcher_mock,
):
    """Disney+ não tem página de busca conhecida; inventar uma levaria a 404."""
    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "PLATFORM_SELECTED",
            "requestId": "busca-disney",
            "payload": {"platform": "DISNEY_PLUS", "openSearch": True},
        })
        websocket.receive_json()

    browser_launcher_mock.open.assert_called_once_with("https://www.disneyplus.com")


def test_play_pause_uses_the_space_bar_on_the_focused_window(
    client,
    dispatcher,
    window_focuser_mock,
    pointer_adapter_mock,
    keyboard_adapter_mock,
    windows_key_event_mock,
):
    """Nem a tecla global de mídia, nem o clique no meio do vídeo.

    A tecla global depende do subsistema de mídia do Windows rotear o evento —
    o mesmo subsistema cuja API ficou pendurada por minutos nesta máquina.

    O clique no centro só acerta o vídeo enquanto ele ocupa o meio da tela, que
    é justamente o que deixa de valer quando ele pausa: medido na tela do
    usuário, pausar a Netflix no plano com anúncios encolhe o player num cartão
    à esquerda e cobre o centro com um anúncio. O botão pausava e não
    despausava, e ainda mirava um link de anunciante."""
    window_focuser_mock.find.return_value = DesktopWindow(
        handle=7, process="chrome.exe", title="Jogo - YouTube",
    )
    window_focuser_mock.center_of.return_value = (640, 360)
    dispatcher.media_session_detector.detect.return_value = MediaSession(
        platform="YOUTUBE", kind="WEB",
    )

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        result = send_media(websocket, dispatcher, "MEDIA_PLAY_PAUSE")

    assert result["type"] == "COMMAND_RESULT"
    # A tecla só chega no player certo com a janela em foco.
    window_focuser_mock.focus.assert_called_once()
    keyboard_adapter_mock.press_key.assert_called_once_with("SPACE")
    pointer_adapter_mock.click.assert_not_called()
    windows_key_event_mock.assert_not_called()


def test_play_pause_falls_back_to_the_media_key_without_a_window(
    client,
    dispatcher,
    window_focuser_mock,
    keyboard_adapter_mock,
    windows_key_event_mock,
):
    """Sem janela para focar, a tecla não teria onde chegar — aí a tecla global
    de mídia é a única tentativa que resta."""
    window_focuser_mock.find.return_value = None
    dispatcher.media_session_detector.detect.return_value = MediaSession(
        platform="YOUTUBE", kind="WEB",
    )

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        send_media(websocket, dispatcher, "MEDIA_PLAY_PAUSE")

    keyboard_adapter_mock.press_key.assert_not_called()
    windows_key_event_mock.assert_called()


def test_spotify_keeps_the_media_key_for_play_pause(
    client,
    dispatcher,
    pointer_adapter_mock,
    windows_key_event_mock,
):
    """O Spotify é aplicativo, não página: clicar no meio da janela acertaria
    a lista de músicas."""
    dispatcher.media_session_detector.detect.return_value = MediaSession(
        platform="SPOTIFY", kind="APP",
    )

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        send_media(websocket, dispatcher, "MEDIA_PLAY_PAUSE")

    pointer_adapter_mock.click.assert_not_called()
    assert windows_key_event_mock.called


def test_play_pause_falls_back_to_the_key_without_a_window(
    client,
    dispatcher,
    window_focuser_mock,
    pointer_adapter_mock,
    windows_key_event_mock,
):
    window_focuser_mock.find.return_value = None
    dispatcher.media_session_detector.detect.return_value = MediaSession(
        platform="YOUTUBE", kind="WEB",
    )

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        send_media(websocket, dispatcher, "MEDIA_PLAY_PAUSE")

    pointer_adapter_mock.click.assert_not_called()
    assert windows_key_event_mock.called


# ── Toque na foto da tela ─────────────────────────────────────────────────

JANELA_DA_NETFLIX = DesktopWindow(handle=7, process="chrome.exe", title="Netflix - Google Chrome")


def preparar_janela(dispatcher, rect=None):
    """Uma janela localizável e um retângulo conhecido para ela."""
    from unittest.mock import Mock

    from app.windows.screen import Retangulo, WindowCapture

    dispatcher.window_focuser.find.return_value = JANELA_DA_NETFLIX
    captura = Mock(spec=WindowCapture)
    captura.retangulo.return_value = rect or Retangulo(1536, 0, 1280, 720)
    dispatcher.window_capture = captura
    return captura


def test_a_tap_on_the_photo_clicks_the_same_spot_on_the_window(
    client, dispatcher, pointer_adapter_mock,
):
    """A conta que faz a feature existir: fração da imagem -> pixel da tela."""
    preparar_janela(dispatcher)

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "SCREEN_TAP",
            "requestId": "tap-1",
            "payload": {"platform": "NETFLIX", "x": 0.5, "y": 0.5},
        })

        resultado = websocket.receive_json()

    assert resultado["data"] == {
        "intent": "SCREEN_CONTROL",
        "action": "SCREEN_TAP",
        "platform": "NETFLIX",
        "executed": True,
    }
    pointer_adapter_mock.move_to.assert_called_once_with(2176, 360)
    pointer_adapter_mock.click.assert_called_once()


def test_the_window_is_brought_to_the_front_before_the_click(client, dispatcher):
    """Clicar numa janela atrás entregaria o clique para quem está na frente."""
    preparar_janela(dispatcher)

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "SCREEN_TAP",
            "requestId": "tap-2",
            "payload": {"platform": "NETFLIX", "x": 0.2, "y": 0.3},
        })
        websocket.receive_json()

    dispatcher.window_focuser.focus.assert_called_once_with(JANELA_DA_NETFLIX)


def test_tapping_a_platform_that_is_not_open_says_so(client, dispatcher):
    dispatcher.window_focuser.find.return_value = None

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "SCREEN_TAP",
            "requestId": "tap-3",
            "payload": {"platform": "MAX", "x": 0.5, "y": 0.5},
        })

        erro = websocket.receive_json()

    assert erro["type"] == "ERROR"
    assert erro["code"] == "SCREEN_CONTROL_FAILED"
    assert "Max" in erro["message"]


def test_choosing_a_profile_clicks_where_it_was_registered(
    client, dispatcher, pointer_adapter_mock, tmp_path,
):
    from app.profiles.store import ProfileStore

    preparar_janela(dispatcher)
    dispatcher.profile_store = ProfileStore(tmp_path / "perfis.json")
    perfil = dispatcher.profile_store.adicionar("NETFLIX", "Gabriel", 0.25, 0.5, None)

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "PROFILE_SELECT",
            "requestId": "perfil-1",
            "payload": {"platform": "NETFLIX", "profileId": perfil.id},
        })

        resultado = websocket.receive_json()

    assert resultado["message"] == "Entrando como Gabriel."
    assert resultado["data"]["action"] == "PROFILE_SELECT"
    pointer_adapter_mock.move_to.assert_called_once_with(1856, 360)


def test_a_profile_that_was_deleted_gives_a_clear_error(client, dispatcher, tmp_path):
    from app.profiles.store import ProfileStore

    preparar_janela(dispatcher)
    dispatcher.profile_store = ProfileStore(tmp_path / "perfis.json")

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "PROFILE_SELECT",
            "requestId": "perfil-2",
            "payload": {"platform": "NETFLIX", "profileId": "nao-existe"},
        })

        erro = websocket.receive_json()

    assert erro["code"] == "PROFILE_NOT_FOUND"


def receber_resultado(websocket) -> dict:
    """A próxima resposta ao comando, pulando o que chega sozinho.

    Com uma janela de plataforma visível, o laço de "tocando agora" passa a
    emitir pelo caminho da janela — e essa mensagem chega no meio.
    """
    for _ in range(5):
        mensagem = websocket.receive_json()
        if mensagem["type"] not in ("NOW_PLAYING", "HEARTBEAT"):
            return mensagem
    raise AssertionError("só chegou mensagem espontânea")


def test_typing_brings_the_platform_to_the_front_first(client, dispatcher):
    """Sem isto o texto ia para a janela que estivesse na frente.

    Foi o "botão sem pegar" relatado: o texto era enviado de verdade, só que
    para o editor de código aberto atrás — e o controle respondia "texto
    enviado", porque enviado ele foi.
    """
    dispatcher.window_focuser.media_window.return_value = JANELA_DA_NETFLIX

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "KEYBOARD_TEXT",
            "requestId": "texto-1",
            "payload": {"text": "o justiceiro"},
        })

        resultado = receber_resultado(websocket)

    assert resultado["data"]["intent"] == "KEYBOARD_CONTROL"
    dispatcher.window_focuser.focus.assert_called_once_with(JANELA_DA_NETFLIX)


def test_typing_still_works_when_no_platform_window_is_open(client, dispatcher):
    """Sem plataforma aberta o texto continua indo: é o comportamento antigo."""
    dispatcher.window_focuser.media_window.return_value = None

    with client.websocket_connect("/ws") as websocket:
        receive_auth_required(websocket)
        pair(websocket, dispatcher)
        websocket.send_json({
            "protocolVersion": 1,
            "type": "KEYBOARD_TEXT",
            "requestId": "texto-2",
            "payload": {"text": "oi"},
        })

        resultado = receber_resultado(websocket)

    assert resultado["success"] is True
    dispatcher.window_focuser.focus.assert_not_called()


def test_the_now_playing_fields_are_a_contract_with_the_phone():
    """O celular valida a mensagem com uma LISTA FECHADA de campos.

    Um campo novo aqui que não seja acrescentado em
    `frontend/src/features/fawkes-remote/protocol.ts` (`isNowPlayingSession`)
    faz o celular DESCARTAR a mensagem inteira. O cartão fica preso em "nada
    tocando" para sempre, sem erro na tela nem no log do servidor — foi
    exatamente o que aconteceu quando `episode` nasceu só deste lado.

    Se este teste falhou porque você acrescentou um campo: acrescente-o também
    no validador do frontend e no teste de lá, e então atualize esta lista.
    """
    from app.schemas.ws import NowPlayingSession

    assert set(NowPlayingSession.model_fields) == {
        "title",
        "episode",
        "artist",
        "app",
        "platform",
        "playing",
        "positionSeconds",
        "durationSeconds",
        "positionStale",
        "titleIsWork",
        "thumbnailId",
        "posterUrl",
        "historyRevision",
    }


# ── O socorro pela janela, que só o CI exercitava ─────────────────────────
#
# Quando a SMTC não responde, a leitura cai para o título da janela aberta. Esse
# caminho passou meses sem UM teste porque nesta máquina o `winsdk` está
# instalado: a leitura vinha pela SMTC e o socorro nunca entrava.
#
# No Linux não há `winsdk`. Em 27/08/2026 o CI caiu com 141 testes de uma vez,
# todos `assert 'HEARTBEAT' == 'NOW_PLAYING'`, e a causa estava na fixture: ela
# zerava `find` e esquecia `media_window`, que devolvia um `Mock`. O socorro
# entrava com um título que não é texto e a leitura inteira morria com
# "'Mock' object is not iterable" — o cartão nunca era enviado, e o celular
# recebia só o batimento.
#
# Estes testes existem para o caminho passar a ser exercitado dos DOIS lados.

@pytest.mark.asyncio
async def test_sem_smtc_a_janela_diz_o_que_esta_tocando(dispatcher, monkeypatch):
    """A metade que faltava: a SMTC ausente, e a janela respondendo por ela."""
    monkeypatch.setattr(dispatcher_module, "smtc_disponivel", lambda: False)
    dispatcher.window_focuser.media_window.return_value = DesktopWindow(
        handle=7, process="chrome.exe", title="Duna: Parte Dois - Netflix - Google Chrome",
    )

    mensagem = await dispatcher._read_now_playing(contar=False)

    assert mensagem["type"] == "NOW_PLAYING"
    assert mensagem["session"]["title"] == "Duna: Parte Dois"


@pytest.mark.asyncio
async def test_sem_smtc_e_sem_janela_nao_ha_cartao(dispatcher, monkeypatch):
    monkeypatch.setattr(dispatcher_module, "smtc_disponivel", lambda: False)
    dispatcher.window_focuser.media_window.return_value = None

    mensagem = await dispatcher._read_now_playing(contar=False)

    assert mensagem["session"] is None


@pytest.mark.asyncio
async def test_um_titulo_que_nao_e_TEXTO_nao_derruba_a_leitura(dispatcher, monkeypatch):
    """O defeito exato do CI, agora como teste.

    Um título que não é texto é entrada inválida vinda de fora — e entrada
    inválida não pode calar o cartão. Era isto que fazia o celular receber só
    batimento: a exceção subia, o laço pulava a volta, e nada dizia por quê a
    não ser uma linha no terminal do servidor.
    """
    monkeypatch.setattr(dispatcher_module, "smtc_disponivel", lambda: False)
    dispatcher.window_focuser.media_window.return_value = DesktopWindow(
        handle=7, process="chrome.exe", title=Mock(),
    )

    mensagem = await dispatcher._read_now_playing(contar=False)

    assert mensagem["type"] == "NOW_PLAYING"
