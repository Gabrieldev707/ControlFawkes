import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Enviar estado inicial
    await websocket.send_json({
        "type": "STATE_UPDATE",
        "state": "CONNECTED"
    })
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Aqui no MVP Fase 1 apenas ecoamos um log e devolvemos resultado genérico
            if message.get("type") == "REMOTE_COMMAND":
                print(f"[WS] Comando recebido: {message}")
                
                await websocket.send_json({
                    "type": "COMMAND_RESULT",
                    "requestId": message.get("requestId", ""),
                    "success": True,
                    "message": "Comando processado (Mock)"
                })
                
    except WebSocketDisconnect:
        print("[WS] Cliente desconectado")
