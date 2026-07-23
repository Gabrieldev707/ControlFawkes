from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.protocol.dispatcher import Dispatcher


router = APIRouter()
dispatcher = Dispatcher()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    if not await dispatcher.connect(websocket):
        return
    try:
        while True:
            # receive() em vez de receive_text(): um frame binário levantava
            # KeyError e escapava do handler, deixando estado preso.
            event = await websocket.receive()
            if event["type"] == "websocket.disconnect":
                break
            raw = event.get("text")
            if raw is None:
                await dispatcher.reject_non_text_frame(websocket)
                continue
            await dispatcher.dispatch(websocket, raw)
    except WebSocketDisconnect:
        pass
    finally:
        # finally, e não apenas no disconnect: qualquer erro precisa soltar o
        # botão do mouse e limpar a sessão.
        await dispatcher.disconnect(websocket)
