"""O perfil de quem usa o controle.

Não é o perfil da Netflix — esse mora em `screen.py` e serve para clicar em
"quem está assistindo?". Este é o histórico do próprio controle: o que foi
assistido neste computador, o que ficou pela metade, e o que combina com isso.

Tudo sai do que o laço de "tocando agora" já observava e descartava. Nada aqui
depende de conta, login ou serviço externo — só o bloco de recomendações, que
precisa do catálogo e some sozinho quando ele está desligado.
"""

from collections import defaultdict
import time

from fastapi import APIRouter, Header, HTTPException, Request

from app.api import websocket as websocket_module
from app.catalog.tmdb import PLATAFORMAS_COM_CATALOGO
from app.history import achievements
from app.security.origins import is_origin_allowed


router = APIRouter()

# Recomendação não muda de minuto em minuto, e cada resposta custa várias idas
# ao TMDB. Meia hora é tempo de sobra para parecer viva.
SEGUNDOS_DE_CACHE = 1800.0

# Quantos títulos do histórico ganham gênero por visita. Enriquecer tudo de uma
# vez faria a primeira abertura da tela esperar por dezenas de requisições.
ENRIQUECIDOS_POR_VEZ = 3

_cache: dict[str, object] = {}


def _autenticar(request: Request, device_id: str | None, token: str | None):
    if not is_origin_allowed(request.headers.get("origin")):
        raise HTTPException(status_code=403, detail="Origem não permitida.")
    dispatcher = websocket_module.dispatcher
    if not device_id or not token:
        raise HTTPException(status_code=401, detail="Autenticação necessária.")
    if not dispatcher.device_store.authenticate(device_id, token):
        raise HTTPException(status_code=401, detail="Token inválido.")
    return dispatcher


@router.get("/profile")
async def perfil(
    request: Request,
    x_device_id: str | None = Header(default=None),
    x_device_token: str | None = Header(default=None),
):
    """O retrato do que foi assistido aqui."""
    dispatcher = _autenticar(request, x_device_id, x_device_token)
    store = dispatcher.history_recorder.store
    tudo = store.listar()

    por_genero: dict[str, float] = defaultdict(float)
    por_plataforma: dict[str, float] = defaultdict(float)
    for item in tudo:
        if item.platform:
            por_plataforma[item.platform] += item.segundos
        for genero in item.generos:
            por_genero[genero] += item.segundos

    def maiores(mapa: dict[str, float], limite: int) -> list[dict]:
        ordenado = sorted(mapa.items(), key=lambda par: par[1], reverse=True)
        return [{"nome": nome, "segundos": round(s)} for nome, s in ordenado[:limite]]

    conquistas = achievements.calcular(tudo)
    return {
        # `como_obra` e não `como_dicionario`: esta lista é de OBRAS, e a
        # posição do último episódio não descreve a obra. Ver `Assistido`.
        "continuar": [item.como_obra() for item in store.continuar(limite=10)],
        "conquistas": [c.como_dicionario() for c in conquistas],
        "progresso": achievements.nivel(conquistas),
        "generos": maiores(por_genero, 5),
        "plataformas": maiores(por_plataforma, 6),
        "totalDeTitulos": len(tudo),
        "totalDeSegundos": round(sum(item.segundos for item in tudo)),
    }


@router.get("/profile/recommendations")
async def recomendacoes(
    request: Request,
    x_device_id: str | None = Header(default=None),
    x_device_token: str | None = Header(default=None),
):
    """"Porque você assistiu X" — e só o que está nos seus serviços."""
    dispatcher = _autenticar(request, x_device_id, x_device_token)
    catalogo = dispatcher.catalog
    store = dispatcher.history_recorder.store

    if catalogo is None or not catalogo.enabled:
        return {"enabled": False, "base": None, "titles": []}

    historico = store.listar()
    if not historico:
        return {"enabled": True, "base": None, "titles": []}

    # A base é o que foi mais assistido: um título que ficou duas horas na tela
    # diz mais sobre o gosto do que o que passou cinco minutos ontem.
    base = max(historico, key=lambda item: item.segundos)

    # Antes do cache, sempre: era isto que estava errado. Com a resposta em
    # cache, a função devolvia cedo e nenhum título novo ganhava capa — o filme
    # que começou hoje ficava sem imagem até o cache vencer, meia hora depois.
    await _descobrir_capas(catalogo, store, historico)

    agora = time.monotonic()
    if (
        _cache.get("base") == base.chave
        and isinstance(_cache.get("em"), float)
        and agora - float(_cache["em"]) < SEGUNDOS_DE_CACHE
    ):
        return _cache["resposta"]

    # Os serviços que aparecem no histórico são a prova de quais ele assina —
    # melhor sinal do que qualquer lista configurada à mão.
    #
    # Só os que têm catálogo de filme. Medido: uma tarde de futebol ao vivo no
    # YouTube bastava para o filtro virar "só o que está no YouTube", e o bloco
    # inteiro sumia da tela — o TMDB não marca filme como assinatura do YouTube.
    plataformas = sorted({
        item.platform for item in historico
        if item.platform in PLATAFORMAS_COM_CATALOGO
    })

    try:
        parecidos = await catalogo.parecidos_com(base.titulo, plataformas, limite=12)
    except Exception:  # noqa: BLE001 - recomendação nunca vira erro na tela
        parecidos = []


    resposta = {
        "enabled": True,
        "base": {"titulo": base.titulo, "platform": base.platform},
        "titles": [
            {"title": d.title, "year": d.year, "posterUrl": d.poster_url}
            for d in parecidos
        ],
        # A tela promete "só o que está nos seus serviços". Quando o histórico
        # não tem nenhum serviço com catálogo, filtro nenhum foi aplicado — e
        # repetir a promessa nesse caso é dizer à pessoa algo que não é verdade.
        "filtrado": bool(plataformas),
    }
    _cache.update({"base": base.chave, "em": agora, "resposta": resposta})
    return resposta


async def _descobrir_capas(catalogo, store, historico) -> None:
    """Pergunta ao catálogo a capa e o gênero de alguns títulos que não têm.

    Poucos por visita: a tela não pode esperar por dezenas de requisições, e o
    que falta hoje aparece na próxima abertura.
    """
    # Só o que o catálogo pode responder. Perguntar ao TMDB pelo nome de um
    # vídeo do YouTube devolve a capa de outra coisa, e ela fica gravada:
    # medido no histórico real, o vlog "CHEGUEI NA SÍRIA, PAÍS DE CONFLITO E
    # RELIGIÃO" ganhou o pôster de um filme e apareceu assim em "continuar
    # assistindo". Sem capa é honesto; com a capa de outro título, não.
    faltando = [
        i for i in historico
        if (not i.generos or not i.poster_url)
        and (i.platform is None or i.platform in PLATAFORMAS_COM_CATALOGO)
    ]
    for item in faltando[:ENRIQUECIDOS_POR_VEZ]:
        try:
            poster, generos = await catalogo.detalhes_de(item.titulo)
        except Exception:  # noqa: BLE001 - capa é enfeite, nunca motivo de erro
            continue
        if poster or generos:
            store.enriquecer(item.chave, poster, generos)


@router.delete("/profile/history")
async def limpar(
    request: Request,
    x_device_id: str | None = Header(default=None),
    x_device_token: str | None = Header(default=None),
):
    """Apaga o histórico inteiro. É o botão que torna o resto aceitável."""
    dispatcher = _autenticar(request, x_device_id, x_device_token)
    _cache.clear()
    if not dispatcher.history_recorder.store.limpar():
        raise HTTPException(status_code=500, detail="Não consegui apagar.")
    return {"cleared": True}
