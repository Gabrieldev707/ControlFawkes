"""Capa da mídia atual, por HTTP.

Vai por fora do WebSocket porque uma imagem em base64 estouraria o limite de
mensagem — que existe justamente para uma conexão não conseguir inundar o
computador. O WebSocket carrega só a identidade da capa; o celular busca os
bytes aqui quando essa identidade muda.

A autenticação é a mesma do resto: o par deviceId/token do pareamento.
"""

from fastapi import APIRouter, Header, HTTPException, Request, Response

from app.api import websocket as websocket_module
from app.security.origins import is_origin_allowed


router = APIRouter()

# As capas da SMTC vêm em JPEG ou PNG; o navegador decide pelo conteúdo, mas o
# cabeçalho evita um sniff desnecessário.
def _tipo_de(dados: bytes) -> str:
    return "image/png" if dados[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"


@router.get("/now-playing/thumbnail/{thumbnail_id}")
async def thumbnail(
    request: Request,
    thumbnail_id: str,
    x_device_id: str | None = Header(default=None),
    x_device_token: str | None = Header(default=None),
):
    if not is_origin_allowed(request.headers.get("origin")):
        raise HTTPException(status_code=403, detail="Origem não permitida.")

    dispatcher = websocket_module.dispatcher
    if not x_device_id or not x_device_token:
        raise HTTPException(status_code=401, detail="Autenticação necessária.")
    if not dispatcher.device_store.authenticate(x_device_id, x_device_token):
        raise HTTPException(status_code=401, detail="Token inválido.")

    dados = dispatcher.thumbnails.get(thumbnail_id)
    if dados is None:
        raise HTTPException(status_code=404, detail="Capa indisponível.")

    return Response(
        content=dados,
        media_type=_tipo_de(dados),
        # A identidade da capa é o hash do conteúdo: se o id é o mesmo, a
        # imagem é a mesma, e o celular pode guardar à vontade.
        headers={"Cache-Control": "private, max-age=86400, immutable"},
    )
