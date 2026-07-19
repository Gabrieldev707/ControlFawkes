import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import TypeAdapter, ValidationError
from app.schemas.ws import ClientMessage, CommandResultMessage, ErrorMessage, StateUpdateMessage, PlatformSelectedMessage

router = APIRouter()

# TypeAdapter to parse our discriminated union
client_message_adapter = TypeAdapter(ClientMessage)

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Enviar estado inicial
    await websocket.send_json(
        StateUpdateMessage(state="connected").model_dump()
    )
    
    try:
        while True:
            data = await websocket.receive_text()
            
            # 1. Check valid JSON
            try:
                raw_json = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json(
                    ErrorMessage(
                        requestId="unknown",
                        code="INVALID_JSON",
                        message="JSON malformado."
                    ).model_dump()
                )
                continue
                
            # 2. Check schema with TypeAdapter
            try:
                message = client_message_adapter.validate_python(raw_json)
            except ValidationError as e:
                # We can determine if it's an unsupported type or invalid payload
                # Usually if 'type' fails discriminator, it's unsupported.
                error_msg = str(e)
                if "Input tag" in error_msg and "found using 'type'" in error_msg:
                    code = "UNSUPPORTED_MESSAGE"
                    msg = "Tipo de mensagem não suportado."
                else:
                    code = "INVALID_PAYLOAD"
                    msg = "Payload inválido."
                
                await websocket.send_json(
                    ErrorMessage(
                        requestId=raw_json.get("requestId", "unknown") if isinstance(raw_json, dict) else "unknown",
                        code=code,
                        message=msg
                    ).model_dump()
                )
                continue
                
            # 3. Handle messages
            try:
                if isinstance(message, PlatformSelectedMessage):
                    print(f"[WS] Plataforma selecionada: {message.payload.platform}")
                    # Retornamos sucesso real sem abrir a plataforma ainda (Fase 1.5)
                    await websocket.send_json(
                        CommandResultMessage(
                            requestId=message.requestId,
                            success=True,
                            message=f"{message.payload.platform} selecionada.",
                            data={"platform": message.payload.platform}
                        ).model_dump()
                    )
                else:
                    # Se houver outros tipos conhecidos mas sem handler
                    await websocket.send_json(
                        ErrorMessage(
                            requestId=message.requestId,
                            code="NOT_IMPLEMENTED",
                            message="Comando conhecido mas sem handler implementado."
                        ).model_dump()
                    )
                    
            except Exception as e:
                print(f"[WS] Erro interno: {e}")
                await websocket.send_json(
                    ErrorMessage(
                        requestId=message.requestId,
                        code="INTERNAL_ERROR",
                        message="Falha inesperada no handler."
                    ).model_dump()
                )

    except WebSocketDisconnect:
        print("[WS] Cliente desconectado")
