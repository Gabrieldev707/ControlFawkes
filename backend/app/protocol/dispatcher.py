import json
import uuid
from typing import Dict
from fastapi import WebSocket
from pydantic import TypeAdapter, ValidationError

from app.schemas.ws import ClientMessage, ErrorMessage, StateUpdateMessage, CommandResultMessage
from app.schemas.auth import (
    AuthRequiredMessage, AuthResultMessage, PairResultMessage,
    AuthMessage, PairDeviceMessage
)
from app.schemas.volume import (
    VolumeGetMessage, VolumeSetMessage, VolumeStepMessage, VolumeToggleMuteMessage,
    VolumeStateMessage
)

from app.security.device_store import DeviceStore
from app.security.pairing import PairingService
from app.windows.volume import WindowsVolumeService, WindowsAPIUnavailable, CoreAudioFailed
from app.protocol.rate_limit import RateLimiter

class Dispatcher:
    def __init__(self, device_store: DeviceStore = None):
        self.device_store = device_store or DeviceStore()
        self.pairing_service = PairingService(self.device_store)
        self.volume_service = WindowsVolumeService()
        self.volume_rate_limiter = RateLimiter(max_ops=20, time_window=1.0)
        
        # map websocket to authenticated deviceId
        self.authenticated_connections: Dict[WebSocket, str] = {}
        self.client_adapter = TypeAdapter(ClientMessage)
        self._rotation_task = None

    async def startup(self) -> None:
        """Inicializa o Dispatcher, gerando o PIN inicial e iniciando a tarefa de expiração."""
        self.pairing_service.initialize()
        if self._rotation_task is None or self._rotation_task.done():
            import asyncio
            self._rotation_task = asyncio.create_task(self._rotation_loop())

    async def shutdown(self) -> None:
        """Encerra graciosamente as tarefas em background do Dispatcher."""
        if self._rotation_task and not self._rotation_task.done():
            import asyncio
            self._rotation_task.cancel()
            try:
                await self._rotation_task
            except asyncio.CancelledError:
                pass

    async def _rotation_loop(self) -> None:
        import asyncio
        while True:
            # We wake up roughly every second to check if it expired.
            # rotate_if_expired itself checks the timestamp safely.
            await asyncio.sleep(1)
            self.pairing_service.rotate_if_expired()

    async def handle_connect(self, websocket: WebSocket):
        await websocket.accept()

    def handle_disconnect(self, websocket: WebSocket):
        if websocket in self.authenticated_connections:
            device_id = self.authenticated_connections[websocket]
            # Decrement connection count or just rely on rate limiter logic (will fix rate limiter later)
            del self.authenticated_connections[websocket]

    async def _send_error(self, websocket: WebSocket, req_id: str, code: str, msg: str):
        err = ErrorMessage(requestId=req_id, code=code, message=msg)
        await websocket.send_json(err.model_dump())

    async def handle_message(self, websocket: WebSocket, data: str):
        if len(data) > 8192:
            await self._send_error(websocket, "unknown", "PAYLOAD_TOO_LARGE", "Mensagem excede 8KB.")
            return

        # 1. Parse JSON
        try:
            raw_json = json.loads(data)
        except json.JSONDecodeError:
            await self._send_error(websocket, "unknown", "INVALID_JSON", "JSON malformado.")
            return

        if not isinstance(raw_json, dict):
            await self._send_error(websocket, "unknown", "INVALID_PAYLOAD", "A mensagem deve ser um objeto JSON.")
            return

        req_id = raw_json.get("requestId", "unknown")
        
        # 2. Extract Type
        msg_type = raw_json.get("type")
        if not msg_type:
            await self._send_error(websocket, req_id, "INVALID_PAYLOAD", "Campo 'type' ausente.")
            return

        # 3. Validate with Pydantic
        try:
            message = self.client_adapter.validate_python(raw_json)
        except ValidationError as e:
            await self._send_error(websocket, req_id, "INVALID_PAYLOAD", "Payload inválido ou campos extras fornecidos.")
            return

        # 4. Routing
        try:
            if isinstance(message, AuthMessage):
                await self._handle_auth(websocket, message)
            elif isinstance(message, PairDeviceMessage):
                await self._handle_pair(websocket, message)
            else:
                # Protected routes
                if websocket not in self.authenticated_connections:
                    await self._send_error(websocket, req_id, "AUTH_REQUIRED", "Autenticação necessária.")
                    return
                
                device_id = self.authenticated_connections[websocket]
                
                # Volume Routes
                if msg_type in ['VOLUME_GET', 'VOLUME_SET', 'VOLUME_STEP', 'VOLUME_TOGGLE_MUTE']:
                    if not self.volume_rate_limiter.check_and_consume(device_id):
                        await self._send_error(websocket, req_id, "RATE_LIMITED", "Muitas requisições de volume.")
                        return
                    await self._handle_volume(websocket, message)
                
                # Platform/Text
                elif msg_type == 'PLATFORM_SELECTED':
                    await websocket.send_json(
                        CommandResultMessage(
                            requestId=req_id, success=True, 
                            message=f"{message.payload.platform} selecionada."
                        ).model_dump()
                    )
                elif msg_type == 'TEXT_COMMAND':
                    await websocket.send_json(
                        CommandResultMessage(
                            requestId=req_id, success=True, 
                            message="Comando de texto recebido."
                        ).model_dump()
                    )

        except WindowsAPIUnavailable:
            await self._send_error(websocket, req_id, "WINDOWS_API_UNAVAILABLE", "API do Windows não disponível neste ambiente.")
        except CoreAudioFailed as e:
            await self._send_error(websocket, req_id, "CORE_AUDIO_FAILED", str(e))
        except Exception as e:
            print(f"[Dispatcher] Erro interno: {e}")
            await self._send_error(websocket, req_id, "INTERNAL_ERROR", "Falha inesperada no servidor.")

    async def _handle_auth(self, websocket: WebSocket, msg: AuthMessage):
        device_id = msg.payload.deviceId
        token = msg.payload.token
        
        is_valid = self.device_store.authenticate_device(device_id, token)
        if is_valid:
            self.authenticated_connections[websocket] = device_id
            res = AuthResultMessage(requestId=msg.requestId, success=True, deviceId=device_id, message="Autenticado com sucesso.")
            await websocket.send_json(res.model_dump())
        else:
            # Blind rejection
            res = AuthResultMessage(requestId=msg.requestId, success=False, message="Token inválido.")
            await websocket.send_json(res.model_dump())

    async def _handle_pair(self, websocket: WebSocket, msg: PairDeviceMessage):
        pin = msg.payload.pin
        device_name = msg.payload.deviceName
        
        success, device_id, token, text = self.pairing_service.attempt_pairing(pin, device_name)
        if success:
            self.authenticated_connections[websocket] = device_id
            res = PairResultMessage(requestId=msg.requestId, success=True, deviceId=device_id, token=token, message=text)
            await websocket.send_json(res.model_dump())
        else:
            res = PairResultMessage(requestId=msg.requestId, success=False, message=text)
            await websocket.send_json(res.model_dump())

    async def _handle_volume(self, websocket: WebSocket, msg: ClientMessage):
        level, muted = 0, False
        
        if isinstance(msg, VolumeGetMessage):
            level, muted = await self.volume_service.get_state()
        elif isinstance(msg, VolumeSetMessage):
            level, muted = await self.volume_service.set_level(msg.payload.level)
        elif isinstance(msg, VolumeStepMessage):
            level, muted = await self.volume_service.step(msg.payload.delta)
        elif isinstance(msg, VolumeToggleMuteMessage):
            level, muted = await self.volume_service.toggle_mute()
            
        res = VolumeStateMessage(requestId=msg.requestId, level=level, muted=muted)
        await websocket.send_json(res.model_dump())
