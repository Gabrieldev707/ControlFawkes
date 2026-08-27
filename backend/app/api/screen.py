"""A tela do computador, e os perfis que moram nela.

Por HTTP e não pelo WebSocket pelo mesmo motivo da capa da mídia: um quadro em
base64 estouraria o limite de mensagem, que existe justamente para uma conexão
não conseguir inundar o computador. O WebSocket carrega o comando — o toque —,
e a imagem vem por aqui.

A autenticação é a mesma do resto: o par deviceId/token do pareamento.
"""

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api import websocket as websocket_module
from app.schemas.platform import Platform
from app.security.origins import is_origin_allowed


router = APIRouter()


class NovoPerfil(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: Platform
    nome: str = Field(min_length=1, max_length=40)
    x: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    y: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)


def _autenticar(request: Request, device_id: str | None, token: str | None):
    if not is_origin_allowed(request.headers.get("origin")):
        raise HTTPException(status_code=403, detail="Origem não permitida.")
    dispatcher = websocket_module.dispatcher
    if not device_id or not token:
        raise HTTPException(status_code=401, detail="Autenticação necessária.")
    if not dispatcher.device_store.authenticate(device_id, token):
        raise HTTPException(status_code=401, detail="Token inválido.")
    return dispatcher


@router.get("/screen/frame/{platform}")
async def frame(
    request: Request,
    platform: Platform,
    x_device_id: str | None = Header(default=None),
    x_device_token: str | None = Header(default=None),
):
    """Um quadro da janela da plataforma, agora."""
    dispatcher = _autenticar(request, x_device_id, x_device_token)

    janela = dispatcher.window_focuser.find(platform)
    if janela is None:
        raise HTTPException(status_code=404, detail="Essa plataforma não está aberta.")

    quadro = dispatcher.window_capture.capturar(janela)
    if quadro is None:
        raise HTTPException(status_code=503, detail="Não consegui fotografar a janela.")

    return Response(
        content=quadro.jpeg,
        media_type="image/jpeg",
        # Guardar isto seria mostrar o passado: cada pedido é um instante novo.
        headers={
            "Cache-Control": "no-store",
            "X-Frame-Width": str(quadro.largura),
            "X-Frame-Height": str(quadro.altura),
        },
    )


@router.get("/screen/profiles")
async def listar_perfis(
    request: Request,
    x_device_id: str | None = Header(default=None),
    x_device_token: str | None = Header(default=None),
):
    dispatcher = _autenticar(request, x_device_id, x_device_token)
    return {
        "platforms": {
            plataforma: [perfil.sem_avatar() for perfil in perfis]
            for plataforma, perfis in dispatcher.profile_store.tudo().items()
        },
    }


@router.get("/screen/profiles/{platform}/{profile_id}/avatar")
async def avatar(
    request: Request,
    platform: Platform,
    profile_id: str,
    x_device_id: str | None = Header(default=None),
    x_device_token: str | None = Header(default=None),
):
    dispatcher = _autenticar(request, x_device_id, x_device_token)
    perfil = dispatcher.profile_store.buscar(platform, profile_id)
    if perfil is None or perfil.avatar is None:
        raise HTTPException(status_code=404, detail="Sem avatar para esse perfil.")
    return Response(
        content=perfil.avatar,
        media_type="image/jpeg",
        # O recorte não muda enquanto o perfil existir, e o id é único.
        headers={"Cache-Control": "private, max-age=86400, immutable"},
    )


@router.post("/screen/profiles", status_code=201)
async def cadastrar_perfil(
    request: Request,
    novo: NovoPerfil,
    x_device_id: str | None = Header(default=None),
    x_device_token: str | None = Header(default=None),
):
    """Guarda o ponto tocado e recorta dali o avatar do serviço.

    O recorte sai da mesma janela que a pessoa acabou de ver, então o botão no
    controle mostra o avatar de verdade da Netflix — não um ícone genérico.
    Sem janela aberta o perfil ainda é guardado, só que sem imagem: a posição é
    o que importa para o clique funcionar.
    """
    dispatcher = _autenticar(request, x_device_id, x_device_token)

    recorte = None
    janela = dispatcher.window_focuser.find(novo.platform)
    if janela is not None:
        recorte = dispatcher.window_capture.recortar_avatar(janela, novo.x, novo.y)

    perfil = dispatcher.profile_store.adicionar(
        novo.platform, novo.nome, novo.x, novo.y, recorte,
    )
    if perfil is None:
        raise HTTPException(
            status_code=409,
            detail="Não consegui guardar. Já são muitos perfis nessa plataforma?",
        )
    return {"platform": novo.platform, "profile": perfil.sem_avatar()}


@router.delete("/screen/profiles/{platform}/{profile_id}")
async def remover_perfil(
    request: Request,
    platform: Platform,
    profile_id: str,
    x_device_id: str | None = Header(default=None),
    x_device_token: str | None = Header(default=None),
):
    dispatcher = _autenticar(request, x_device_id, x_device_token)
    if not dispatcher.profile_store.remover(platform, profile_id):
        raise HTTPException(status_code=404, detail="Esse perfil não existe.")
    return {"removed": True}
