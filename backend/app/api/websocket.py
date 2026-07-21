from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.protocol.dispatcher import Dispatcher


router = APIRouter()
dispatcher = Dispatcher()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await dispatcher.connect(websocket)
    try:
        while True:
            await dispatcher.dispatch(websocket, await websocket.receive_text())
    except WebSocketDisconnect:
        await dispatcher.disconnect(websocket)
