"""Configurar e conferir a chave do catálogo, pelo próprio controle.

Sem isto, a única forma de ligar o catálogo era definir uma variável de
ambiente e reiniciar o servidor — e descobrir se a chave prestava só na
próxima busca, sem saber se o silêncio era chave errada, rede ou título
inexistente.

A verificação é uma busca real. É o único jeito honesto: uma chave pode ter o
formato certo e estar revogada.
"""

import time

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api import websocket as websocket_module
from app.security.origins import is_origin_allowed


router = APIRouter()

# Título usado no teste. Escolhido por ser conhecido em qualquer região e ter
# provedores em quase todas: se a chave presta, este acha alguma coisa.
TITULO_DE_TESTE = "Interestelar"


class ChaveDoCatalogo(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    apiKey: str = Field(min_length=1, max_length=200)


def _autenticado(device_id: str | None, token: str | None):
    dispatcher = websocket_module.dispatcher
    if not device_id or not token:
        raise HTTPException(status_code=401, detail="Autenticação necessária.")
    if not dispatcher.device_store.authenticate(device_id, token):
        raise HTTPException(status_code=401, detail="Token inválido.")
    return dispatcher


def _origem_permitida(request: Request) -> None:
    if not is_origin_allowed(request.headers.get("origin")):
        raise HTTPException(status_code=403, detail="Origem não permitida.")


# Os destaques mudam de dia, não de minuto. Sem cache, cada abertura da tela
# dispararia uma chamada por serviço — e são cinco.
DESTAQUES_VALIDOS_POR = 6 * 60 * 60
_destaques: dict[str, tuple[float, list[dict]]] = {}


@router.get("/catalog/highlights")
async def destaques(
    request: Request,
    x_device_id: str | None = Header(default=None),
    x_device_token: str | None = Header(default=None),
):
    """O que está em alta em cada serviço, com pôster.

    A tela de plataformas era uma grade de seis logotipos — não dizia nada
    sobre o que há para assistir hoje. Isto é o que transforma "escolha um
    serviço" em "escolha um filme".
    """
    _origem_permitida(request)
    catalogo = _autenticado(x_device_id, x_device_token).catalog

    if not catalogo.enabled:
        # Sem catálogo a tela continua existindo com os logotipos: a lista
        # vazia é a resposta honesta, não um erro.
        return {"enabled": False, "rows": []}

    agora = time.monotonic()
    guardado = _destaques.get(catalogo.region)
    if guardado is not None and agora - guardado[0] < DESTAQUES_VALIDOS_POR:
        return {"enabled": True, "rows": guardado[1]}

    linhas: list[dict] = []
    for plataforma in ("NETFLIX", "MAX", "DISNEY_PLUS", "PRIME_VIDEO"):
        try:
            achados = await catalogo.highlights(plataforma)
        except Exception:  # noqa: BLE001 - um serviço que falha não some a tela
            continue
        if not achados:
            continue
        linhas.append({
            "platform": plataforma,
            "titles": [
                {"title": d.title, "year": d.year, "posterUrl": d.poster_url}
                for d in achados
            ],
        })

    if linhas:
        _destaques[catalogo.region] = (agora, linhas)
    return {"enabled": True, "rows": linhas}


@router.get("/catalog/tmdb")
async def estado_do_catalogo(
    request: Request,
    x_device_id: str | None = Header(default=None),
    x_device_token: str | None = Header(default=None),
):
    _origem_permitida(request)
    catalogo = _autenticado(x_device_id, x_device_token).catalog

    return {
        "enabled": catalogo.enabled,
        "source": catalogo.key_source,
        "region": catalogo.region,
        # Com a variável de ambiente definida, colar chave aqui não teria
        # efeito. Dizer isso é melhor do que aceitar e não mudar nada.
        "envOverrides": catalogo.env_key_wins,
    }


@router.post("/catalog/tmdb")
async def salvar_chave(
    request: Request,
    payload: ChaveDoCatalogo,
    x_device_id: str | None = Header(default=None),
    x_device_token: str | None = Header(default=None),
):
    _origem_permitida(request)
    catalogo = _autenticado(x_device_id, x_device_token).catalog

    if catalogo.env_key_wins:
        raise HTTPException(
            status_code=409,
            detail=(
                "A chave está definida por variável de ambiente e tem "
                "prioridade. Remova CONTROLFAWKES_TMDB_KEY para configurar "
                "por aqui."
            ),
        )

    # Duas perguntas separadas, porque têm respostas diferentes: a chave é
    # aceita? e, sendo aceita, o caminho inteiro devolve algo útil? Misturar as
    # duas faria "não achei o título" virar "sua chave está errada".
    try:
        chave_aceita = await catalogo.check_key(payload.apiKey)
    except Exception as error:  # noqa: BLE001 - rede, formato, o que for
        raise HTTPException(
            status_code=502,
            detail="Não foi possível falar com o TMDB. Verifique a internet.",
        ) from error

    if not chave_aceita:
        raise HTTPException(
            status_code=422,
            detail=(
                "O TMDB recusou esta chave. Confira se copiou a chave da API "
                "(v3) inteira, sem espaços."
            ),
        )

    try:
        encontrado = await catalogo.verify(payload.apiKey)
    except Exception as error:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail="Não foi possível falar com o TMDB. Verifique a internet.",
        ) from error

    if encontrado is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "A chave é válida, mas a busca de teste não devolveu nada. "
                "Verifique a região configurada."
            ),
        )

    if not catalogo.save_key(payload.apiKey):
        raise HTTPException(status_code=500, detail="Não foi possível guardar a chave.")

    return {
        "enabled": True,
        "source": catalogo.key_source,
        "region": catalogo.region,
        # A prova de que funcionou, com o resultado real da busca de teste.
        "sample": {
            "title": encontrado.title,
            "year": encontrado.year,
            "platforms": encontrado.platforms,
        },
    }


@router.delete("/catalog/tmdb")
async def esquecer_chave(
    request: Request,
    x_device_id: str | None = Header(default=None),
    x_device_token: str | None = Header(default=None),
):
    _origem_permitida(request)
    catalogo = _autenticado(x_device_id, x_device_token).catalog

    if not catalogo.forget_key():
        raise HTTPException(status_code=500, detail="Não foi possível remover a chave.")

    return {"enabled": catalogo.enabled, "source": catalogo.key_source}
