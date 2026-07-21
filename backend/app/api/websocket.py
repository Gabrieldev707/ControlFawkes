from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.protocol.dispatcher import Dispatcher

router = APIRouter()
dispatcher = Dispatcher()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await dispatcher.handle_connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            await dispatcher.handle_message(websocket, data)

    except WebSocketDisconnect:
        dispatcher.handle_disconnect(websocket)
        print("[WS] Cliente desconectado")
