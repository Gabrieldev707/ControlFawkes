import json

from fastapi import WebSocket
from pydantic import TypeAdapter, ValidationError

from app.schemas.auth import (
    AuthMessage,
    AuthResultMessage,
    PairDeviceMessage,
    PairResultMessage,
)
from app.schemas.ws import (
    ClientMessage,
    CommandResultMessage,
    NeedsPlatformMessage,
    NavigationCommandData,
    ErrorCode,
    ErrorMessage,
    HelpCommandData,
    KeyboardCommandData,
    KeyboardKeyMessage,
    KeyboardTextMessage,
    MediaCommandData,
    MediaControlMessage,
    PointerClickMessage,
    PointerCommandData,
    PointerDoubleClickMessage,
    PointerDownMessage,
    PointerMoveMessage,
    PointerRightClickMessage,
    PointerScrollMessage,
    PointerUpMessage,
    Platform,
    PlatformCommandData,
    PlatformSelectedMessage,
    SearchMediaCommandData,
    SearchMediaMessage,
    StateUpdateMessage,
    TextCommandMessage,
    VolumeCommandData,
    VolumeDeltaMessage,
    VolumeGetMessage,
    VolumeMuteToggleMessage,
    VolumeSetMessage,
)
from app.commands.parser import (
    HELP_COMMANDS,
    PLATFORM_LABELS,
    NeedsPlatformIntent,
    OpenPlatformIntent,
    SearchMediaIntent,
    ShowHelpIntent,
    parse_command,
)
from app.security.device_store import DeviceStore
from app.security.origins import is_origin_allowed
from app.security.pairing import PairingService
from app.platforms.launcher import PlatformLauncher
from app.platforms.registry import suggested_search_platforms
from app.platforms.search import MediaSearchLauncher
from app.media.actions import MEDIA_ACTIONS, MEDIA_ACTION_LABELS
from app.media.session import WindowsMediaSessionDetector
from app.media.windows_adapter import WindowsMediaAdapter
from app.schemas.volume import VOLUME_ACTIONS
from app.windows.volume import WindowsVolumeAdapter, WindowsVolumeError
from app.input.pointer import PointerRateLimiter, WindowsPointerAdapter
from app.schemas.pointer import POINTER_ACTIONS
from app.input.keyboard import WindowsKeyboardAdapter
from app.schemas.keyboard import KEYBOARD_ACTIONS
from app.schemas.navigation import (
    NAVIGATION_ACTIONS,
    NAVIGATION_KEYS,
    NAVIGATION_LABELS,
    REPEATABLE_ACTIONS,
    NavigationMessage,
)


WS_POLICY_VIOLATION = 1008
WS_TRY_AGAIN_LATER = 1013

KNOWN_CLIENT_TYPES = {
    "AUTH",
    "PAIR_DEVICE",
    "PLATFORM_SELECTED",
    "TEXT_COMMAND",
    "SEARCH_MEDIA",
    *MEDIA_ACTIONS,
    *VOLUME_ACTIONS,
    *POINTER_ACTIONS,
    *KEYBOARD_ACTIONS,
    *NAVIGATION_ACTIONS,
}


class Dispatcher:
    # Acima do teto do touchpad (60/s), para não atrapalhar o uso legítimo.
    MAX_MESSAGES_PER_SECOND = 120
    MAX_CONNECTIONS = 32
    # Auto-repeat confortável ao segurar a seta, sem virar inundação.
    MAX_NAVIGATION_PER_SECOND = 20
    # Confirmar/voltar: no máximo ~3 por segundo, contra toque duplo acidental.
    MAX_NON_REPEATABLE_PER_SECOND = 3

    def __init__(
        self,
        device_store: DeviceStore | None = None,
        pairing_service: PairingService | None = None,
        platform_launcher: PlatformLauncher | None = None,
        media_search_launcher: MediaSearchLauncher | None = None,
        media_adapter: WindowsMediaAdapter | None = None,
        media_session_detector: WindowsMediaSessionDetector | None = None,
        volume_adapter: WindowsVolumeAdapter | None = None,
        pointer_adapter: WindowsPointerAdapter | None = None,
        pointer_rate_limiter: PointerRateLimiter | None = None,
        keyboard_adapter: WindowsKeyboardAdapter | None = None,
        message_rate_limiter: PointerRateLimiter | None = None,
        navigation_rate_limiter: PointerRateLimiter | None = None,
    ) -> None:
        self.device_store = device_store or DeviceStore()
        self.pairing_service = pairing_service or PairingService(self.device_store)
        self.platform_launcher = platform_launcher or PlatformLauncher()
        self.media_search_launcher = media_search_launcher or MediaSearchLauncher()
        self.media_adapter = media_adapter or WindowsMediaAdapter()
        self.media_session_detector = media_session_detector or WindowsMediaSessionDetector()
        self.volume_adapter = volume_adapter or WindowsVolumeAdapter()
        self.pointer_adapter = pointer_adapter or WindowsPointerAdapter()
        self.pointer_rate_limiter = pointer_rate_limiter or PointerRateLimiter()
        self.keyboard_adapter = keyboard_adapter or WindowsKeyboardAdapter()
        self.message_rate_limiter = message_rate_limiter or PointerRateLimiter(
            max_updates=self.MAX_MESSAGES_PER_SECOND,
        )
        self.navigation_rate_limiter = navigation_rate_limiter or PointerRateLimiter(
            max_updates=self.MAX_NAVIGATION_PER_SECOND,
        )
        self.navigation_repeat_guard = PointerRateLimiter(
            max_updates=self.MAX_NON_REPEATABLE_PER_SECOND,
        )
        self._client_adapter = TypeAdapter(ClientMessage)
        self._authenticated: dict[WebSocket, str] = {}
        self._held_pointer_buttons: set[WebSocket] = set()
        self._connections: set[WebSocket] = set()

    async def startup(self) -> None:
        self.pairing_service.initialize()

    async def connect(self, websocket: WebSocket) -> bool:
        """Aceita a conexão. Retorna False quando ela foi recusada."""
        if not is_origin_allowed(websocket.headers.get("origin")):
            await websocket.close(code=WS_POLICY_VIOLATION)
            return False

        if len(self._connections) >= self.MAX_CONNECTIONS:
            await websocket.close(code=WS_TRY_AGAIN_LATER)
            return False

        self.pairing_service.initialize()
        await websocket.accept()
        self._connections.add(websocket)
        await self._send_state(websocket, "AUTH_REQUIRED", "Autenticação necessária.")
        return True

    async def reject_non_text_frame(self, websocket: WebSocket) -> None:
        await self._send_error(websocket, "unknown", "INVALID_PAYLOAD", "Frame não suportado.")

    async def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._held_pointer_buttons:
            self.pointer_adapter.pointer_up()
            self._held_pointer_buttons.discard(websocket)
        self.pointer_rate_limiter.clear(websocket)
        self.message_rate_limiter.clear(websocket)
        self.navigation_rate_limiter.clear(websocket)
        for action in NAVIGATION_ACTIONS:
            self.navigation_repeat_guard.clear((websocket, action))
        self._authenticated.pop(websocket, None)
        self._connections.discard(websocket)

    async def _send_state(self, websocket: WebSocket, state: str, message: str) -> None:
        response = StateUpdateMessage(state=state, message=message)
        await websocket.send_json(response.model_dump())

    async def _send_error(
        self,
        websocket: WebSocket,
        request_id: str,
        code: ErrorCode,
        message: str,
    ) -> None:
        response = ErrorMessage(requestId=request_id, code=code, message=message)
        await websocket.send_json(response.model_dump())

    async def dispatch(self, websocket: WebSocket, raw: str) -> None:
        # Antes de qualquer processamento: limita inundação por conexão,
        # inclusive de mensagens ainda não autenticadas.
        if not self.message_rate_limiter.allow(websocket):
            await self._send_error(
                websocket,
                "unknown",
                "RATE_LIMITED",
                "Mensagens demais. Tente novamente.",
            )
            return

        try:
            raw_size = len(raw.encode("utf-8"))
        except UnicodeEncodeError:
            await self._send_error(websocket, "unknown", "INVALID_PAYLOAD", "Payload inválido.")
            return

        if raw_size > 8192:
            await self._send_error(websocket, "unknown", "INVALID_PAYLOAD", "Mensagem muito grande.")
            return

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            await self._send_error(websocket, "unknown", "INVALID_JSON", "JSON malformado.")
            return

        if not isinstance(payload, dict):
            await self._send_error(websocket, "unknown", "INVALID_PAYLOAD", "Payload inválido.")
            return

        raw_request_id = payload.get("requestId")
        request_id = raw_request_id if isinstance(raw_request_id, str) and raw_request_id else "unknown"

        protocol_version = payload.get("protocolVersion")
        if type(protocol_version) is not int or protocol_version != 1:
            await self._send_error(
                websocket,
                request_id,
                "PROTOCOL_VERSION_MISMATCH",
                "Versão de protocolo incompatível.",
            )
            return

        message_type = payload.get("type")
        if not isinstance(message_type, str):
            await self._send_error(websocket, request_id, "INVALID_PAYLOAD", "Campo type inválido.")
            return
        if message_type not in KNOWN_CLIENT_TYPES:
            await self._send_error(
                websocket,
                request_id,
                "UNSUPPORTED_MESSAGE",
                "Tipo de mensagem não suportado.",
            )
            return

        try:
            message = self._client_adapter.validate_python(payload)
        except ValidationError:
            await self._send_error(websocket, request_id, "INVALID_PAYLOAD", "Payload inválido.")
            return

        if isinstance(message, PairDeviceMessage):
            await self._pair(websocket, message)
            return
        if isinstance(message, AuthMessage):
            await self._authenticate(websocket, message)
            return
        if websocket not in self._authenticated:
            await self._send_error(websocket, message.requestId, "UNAUTHORIZED", "Autenticação necessária.")
            return

        if isinstance(message, PlatformSelectedMessage):
            await self._handle_open_platform(
                websocket,
                message.requestId,
                message.payload.platform,
            )
            return

        if isinstance(message, TextCommandMessage):
            await self._handle_text_command(websocket, message)
            return

        if isinstance(message, SearchMediaMessage):
            await self._handle_search_media(
                websocket,
                message.requestId,
                SearchMediaIntent(
                    type="SEARCH_MEDIA",
                    platform=message.payload.platform,
                    query=message.payload.query,
                ),
            )
            return

        if isinstance(message, MediaControlMessage):
            await self._handle_media_control(websocket, message)
            return

        if isinstance(
            message,
            (VolumeGetMessage, VolumeSetMessage, VolumeDeltaMessage, VolumeMuteToggleMessage),
        ):
            await self._handle_volume_control(websocket, message)
            return

        if isinstance(
            message,
            (
                PointerMoveMessage,
                PointerClickMessage,
                PointerDoubleClickMessage,
                PointerRightClickMessage,
                PointerScrollMessage,
                PointerDownMessage,
                PointerUpMessage,
            ),
        ):
            await self._handle_pointer_control(websocket, message)
            return

        if isinstance(message, (KeyboardTextMessage, KeyboardKeyMessage)):
            await self._handle_keyboard_control(websocket, message)
            return

        if isinstance(message, NavigationMessage):
            await self._handle_navigation(websocket, message)
            return

        await self._send_error(
            websocket,
            message.requestId,
            "NOT_IMPLEMENTED",
            "Comando conhecido, mas ainda não implementado.",
        )

    async def _handle_text_command(
        self,
        websocket: WebSocket,
        message: TextCommandMessage,
    ) -> None:
        await self._send_state(websocket, "BUSY", "Processando comando...")
        intent = parse_command(message.payload.query)

        if isinstance(intent, OpenPlatformIntent):
            await self._handle_open_platform(
                websocket,
                message.requestId,
                intent.platform,
            )
        elif isinstance(intent, SearchMediaIntent):
            await self._handle_search_media(
                websocket,
                message.requestId,
                intent,
            )
        elif isinstance(intent, NeedsPlatformIntent):
            await self._ask_where_to_search(websocket, message.requestId, intent)
        elif isinstance(intent, ShowHelpIntent):
            response = CommandResultMessage(
                requestId=message.requestId,
                message="Estes são os comandos disponíveis.",
                data=HelpCommandData(commands=HELP_COMMANDS),
            )
            await websocket.send_json(response.model_dump())
        else:
            await self._send_error(
                websocket,
                message.requestId,
                "UNKNOWN_COMMAND",
                "Não entendi esse comando.",
            )

        await self._send_state(websocket, "READY", "Computador pronto.")

    async def _ask_where_to_search(
        self,
        websocket: WebSocket,
        request_id: str,
        intent: NeedsPlatformIntent,
    ) -> None:
        response = NeedsPlatformMessage(
            requestId=request_id,
            query=intent.query,
            suggestedPlatforms=suggested_search_platforms(intent.music_hint),
        )
        await websocket.send_json(response.model_dump())

    async def _handle_open_platform(
        self,
        websocket: WebSocket,
        request_id: str,
        platform: Platform,
    ) -> None:
        label = PLATFORM_LABELS[platform]
        launch = self.platform_launcher.open(platform)
        if not launch.executed or launch.strategy is None:
            error_message = (
                "Google Chrome não foi encontrado no computador."
                if launch.error == "CHROME_NOT_FOUND"
                else f"Não foi possível abrir o {label}."
            )
            await self._send_error(
                websocket,
                request_id,
                "PLATFORM_OPEN_FAILED",
                error_message,
            )
            return

        response = CommandResultMessage(
            requestId=request_id,
            message=f"{label} aberto.",
            data=PlatformCommandData(
                platform=platform,
                executed=True,
                strategy=launch.strategy,
            ),
        )
        await websocket.send_json(response.model_dump())

    async def _handle_search_media(
        self,
        websocket: WebSocket,
        request_id: str,
        intent: SearchMediaIntent,
    ) -> None:
        label = PLATFORM_LABELS[intent.platform]
        launch = self.media_search_launcher.search(intent.platform, intent.query)
        if not launch.executed or launch.strategy is None:
            await self._send_error(
                websocket,
                request_id,
                "MEDIA_SEARCH_FAILED",
                f"Não foi possível abrir a pesquisa no {label}.",
            )
            return

        response = CommandResultMessage(
            requestId=request_id,
            message=f"Pesquisa aberta no {label}.",
            data=SearchMediaCommandData(
                platform=intent.platform,
                strategy=launch.strategy,
            ),
        )
        await websocket.send_json(response.model_dump())

    async def _handle_media_control(
        self,
        websocket: WebSocket,
        message: MediaControlMessage,
    ) -> None:
        session = self.media_session_detector.detect()
        if session is None:
            await self._send_error(
                websocket,
                message.requestId,
                "MEDIA_SESSION_NOT_FOUND",
                "Nenhuma plataforma de mídia ativa foi identificada.",
            )
            return

        label = PLATFORM_LABELS[session.platform]
        if not self.media_adapter.supports(message.type, session.platform):
            await self._send_error(
                websocket,
                message.requestId,
                "MEDIA_ACTION_UNSUPPORTED",
                f"{MEDIA_ACTION_LABELS[message.type]} não é suportado no {label}.",
            )
            return

        if not self.media_adapter.execute(message.type, session.platform):
            await self._send_error(
                websocket,
                message.requestId,
                "MEDIA_CONTROL_FAILED",
                "Controle de mídia indisponível.",
            )
            return

        response = CommandResultMessage(
            requestId=message.requestId,
            message=f"Comando enviado ao {label}.",
            data=MediaCommandData(
                action=message.type,
                platform=session.platform,
                session=session.kind,
            ),
        )
        await websocket.send_json(response.model_dump())

    async def _handle_volume_control(
        self,
        websocket: WebSocket,
        message: VolumeGetMessage
        | VolumeSetMessage
        | VolumeDeltaMessage
        | VolumeMuteToggleMessage,
    ) -> None:
        try:
            if isinstance(message, VolumeGetMessage):
                state = await self.volume_adapter.get_state()
            elif isinstance(message, VolumeSetMessage):
                state = await self.volume_adapter.set_level(message.payload.level)
            elif isinstance(message, VolumeDeltaMessage):
                state = await self.volume_adapter.change_level(message.payload.delta)
            else:
                state = await self.volume_adapter.toggle_mute()
        except WindowsVolumeError:
            await self._send_error(
                websocket,
                message.requestId,
                "SYSTEM_VOLUME_FAILED",
                "Controle de volume indisponível.",
            )
            return

        response_message = (
            f"Mudo {'ativado' if state.muted else 'desativado'}. Volume: {state.level}%."
            if isinstance(message, VolumeMuteToggleMessage)
            else f"Volume: {state.level}%."
        )
        response = CommandResultMessage(
            requestId=message.requestId,
            message=response_message,
            data=VolumeCommandData(
                action=message.type,
                level=state.level,
                muted=state.muted,
            ),
        )
        await websocket.send_json(response.model_dump())

    async def _handle_pointer_control(
        self,
        websocket: WebSocket,
        message: PointerMoveMessage
        | PointerClickMessage
        | PointerDoubleClickMessage
        | PointerRightClickMessage
        | PointerScrollMessage
        | PointerDownMessage
        | PointerUpMessage,
    ) -> None:
        if isinstance(message, PointerMoveMessage):
            if not self.pointer_rate_limiter.allow(websocket):
                await self._send_error(
                    websocket,
                    message.requestId,
                    "POINTER_RATE_LIMITED",
                    "Movimento do touchpad limitado.",
                )
                return
            executed = self.pointer_adapter.move(message.payload.dx, message.payload.dy)
        elif isinstance(message, PointerClickMessage):
            executed = self.pointer_adapter.click()
        elif isinstance(message, PointerDoubleClickMessage):
            executed = self.pointer_adapter.double_click()
        elif isinstance(message, PointerRightClickMessage):
            executed = self.pointer_adapter.right_click()
        elif isinstance(message, PointerScrollMessage):
            executed = self.pointer_adapter.scroll(message.payload.delta)
        elif isinstance(message, PointerDownMessage):
            executed = self.pointer_adapter.pointer_down()
        else:
            executed = self.pointer_adapter.pointer_up()

        if not executed:
            await self._send_error(
                websocket,
                message.requestId,
                "POINTER_CONTROL_FAILED",
                "Touchpad indisponível.",
            )
            return

        if isinstance(message, PointerDownMessage):
            self._held_pointer_buttons.add(websocket)
        elif isinstance(message, PointerUpMessage):
            self._held_pointer_buttons.discard(websocket)

        response = CommandResultMessage(
            requestId=message.requestId,
            message="Comando do touchpad executado.",
            data=PointerCommandData(action=message.type),
        )
        await websocket.send_json(response.model_dump())

    async def _handle_keyboard_control(
        self,
        websocket: WebSocket,
        message: KeyboardTextMessage | KeyboardKeyMessage,
    ) -> None:
        if isinstance(message, KeyboardTextMessage):
            executed = self.keyboard_adapter.write_text(message.payload.text)
            response_message = "Texto enviado."
        else:
            executed = self.keyboard_adapter.press_key(message.payload.key)
            response_message = "Tecla enviada."

        if not executed:
            await self._send_error(
                websocket,
                message.requestId,
                "KEYBOARD_CONTROL_FAILED",
                "Teclado remoto indisponível.",
            )
            return

        response = CommandResultMessage(
            requestId=message.requestId,
            message=response_message,
            data=KeyboardCommandData(action=message.type),
        )
        await websocket.send_json(response.model_dump())

    async def _handle_navigation(
        self,
        websocket: WebSocket,
        message: NavigationMessage,
    ) -> None:
        # Limite próprio, separado do teclado: o direcional repete ao segurar a
        # seta, e uma repetição acelerada não pode consumir a cota do teclado.
        if not self.navigation_rate_limiter.allow(websocket):
            await self._send_error(
                websocket,
                message.requestId,
                "NAVIGATION_RATE_LIMITED",
                "Navegação rápida demais.",
            )
            return

        # Confirmar e voltar não repetem: entrariam em vários itens ou sairiam
        # de várias telas de uma vez.
        if message.type not in REPEATABLE_ACTIONS:
            if not self.navigation_repeat_guard.allow((websocket, message.type)):
                await self._send_error(
                    websocket,
                    message.requestId,
                    "NAVIGATION_RATE_LIMITED",
                    "Aguarde antes de repetir esse comando.",
                )
                return

        if not self.keyboard_adapter.press_key(NAVIGATION_KEYS[message.type]):
            await self._send_error(
                websocket,
                message.requestId,
                "NAVIGATION_FAILED",
                "Navegação indisponível.",
            )
            return

        response = CommandResultMessage(
            requestId=message.requestId,
            message=f"{NAVIGATION_LABELS[message.type]} enviado.",
            data=NavigationCommandData(action=message.type),
        )
        await websocket.send_json(response.model_dump())

    async def _pair(self, websocket: WebSocket, message: PairDeviceMessage) -> None:
        result = self.pairing_service.attempt(
            message.payload.pin,
            message.payload.deviceName,
        )
        if not result.success or not result.device_id or not result.token:
            code: ErrorCode = result.code if result.code in {
                "PIN_INVALID", "PIN_EXPIRED", "TOO_MANY_ATTEMPTS", "INTERNAL_ERROR"
            } else "INTERNAL_ERROR"
            await self._send_error(websocket, message.requestId, code, result.message)
            return

        self._authenticated[websocket] = result.device_id
        response = PairResultMessage(
            requestId=message.requestId,
            message=result.message,
            deviceId=result.device_id,
            token=result.token,
        )
        await websocket.send_json(response.model_dump())
        await self._send_state(websocket, "READY", "Computador pronto.")

    async def _authenticate(self, websocket: WebSocket, message: AuthMessage) -> None:
        if not self.device_store.authenticate(message.payload.deviceId, message.payload.token):
            await self._send_error(websocket, message.requestId, "INVALID_TOKEN", "Token inválido.")
            return

        self._authenticated[websocket] = message.payload.deviceId
        response = AuthResultMessage(
            requestId=message.requestId,
            message="Autenticação concluída.",
        )
        await websocket.send_json(response.model_dump())
        await self._send_state(websocket, "READY", "Computador pronto.")
