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
    ErrorCode,
    ErrorMessage,
    HelpCommandData,
    Platform,
    PlatformCommandData,
    PlatformSelectedMessage,
    StateUpdateMessage,
    TextCommandMessage,
)
from app.commands.parser import (
    HELP_COMMANDS,
    PLATFORM_LABELS,
    OpenPlatformIntent,
    ShowHelpIntent,
    parse_command,
)
from app.security.device_store import DeviceStore
from app.security.pairing import PairingService
from app.platforms.launcher import PlatformLauncher


KNOWN_CLIENT_TYPES = {"AUTH", "PAIR_DEVICE", "PLATFORM_SELECTED", "TEXT_COMMAND"}


class Dispatcher:
    def __init__(
        self,
        device_store: DeviceStore | None = None,
        pairing_service: PairingService | None = None,
        platform_launcher: PlatformLauncher | None = None,
    ) -> None:
        self.device_store = device_store or DeviceStore()
        self.pairing_service = pairing_service or PairingService(self.device_store)
        self.platform_launcher = platform_launcher or PlatformLauncher()
        self._client_adapter = TypeAdapter(ClientMessage)
        self._authenticated: dict[WebSocket, str] = {}

    async def startup(self) -> None:
        self.pairing_service.initialize()

    async def connect(self, websocket: WebSocket) -> None:
        self.pairing_service.initialize()
        await websocket.accept()
        await self._send_state(websocket, "AUTH_REQUIRED", "Autenticação necessária.")

    async def disconnect(self, websocket: WebSocket) -> None:
        self._authenticated.pop(websocket, None)

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
        if len(raw.encode("utf-8")) > 8192:
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

    async def _handle_open_platform(
        self,
        websocket: WebSocket,
        request_id: str,
        platform: Platform,
    ) -> None:
        if platform != "SPOTIFY":
            response = CommandResultMessage(
                requestId=request_id,
                message=f"Comando reconhecido: abrir {PLATFORM_LABELS[platform]}.",
                data=PlatformCommandData(platform=platform),
            )
            await websocket.send_json(response.model_dump())
            return

        if not self.platform_launcher.open(platform):
            await self._send_error(
                websocket,
                request_id,
                "PLATFORM_OPEN_FAILED",
                "Não foi possível abrir o Spotify.",
            )
            return

        response = CommandResultMessage(
            requestId=request_id,
            message="Spotify aberto.",
            data=PlatformCommandData(platform=platform, executed=True),
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
