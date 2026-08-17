"""A porta por onde os eventos do navegador entram — e as três trancas dela.

Esta é a única rota do ControlFawkes que não existe para o celular. Ela existe
para o Native Host, que roda na mesma máquina, e por isso é mais fechada do que
todas as outras em vez de menos.

    1. loopback        só de 127.0.0.1 / ::1. Um pedido vindo da rede local é
                       recusado antes de qualquer outra coisa.
    2. sem `Origin`    todo `fetch` de página carrega `Origin`; o host, que é
                       um cliente HTTP comum, não carrega. Uma aba do navegador
                       não consegue não mandar esse cabeçalho.
    3. credencial      o segredo de `bridge/credencial.py`, conferido em TODA
                       mensagem, sem sessão e sem memória de quem já passou.

As três são independentes de propósito. A primeira sozinha não basta: qualquer
página aberta consegue falar com `127.0.0.1`, e foi exatamente esse o achado que
descartou o WebSocket em localhost no Spike B.

E a validação da Fase 6 continua inteira depois das trancas. Autenticar é
responder "quem mandou?"; validar é responder "isto é utilizável?". Um host
autenticado que mande `currentTime` além do fim do vídeo continua sendo
recusado — a extensão lê um DOM que ninguém aqui controla, e ser nossa não a
torna confiável.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Header, HTTPException, Request

from app.bridge.credencial import CABECALHO, CredencialDaPonte
from app.bridge.eventos import Recusa, validar


router = APIRouter()

credencial = CredencialDaPonte()

# `::ffff:127.0.0.1` aparece quando o socket é IPv6 atendendo um cliente IPv4.
ENDERECOS_LOCAIS = frozenset({"127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost"})


def _exigir_loopback(request: Request) -> None:
    cliente = request.client.host if request.client else None
    if cliente not in ENDERECOS_LOCAIS:
        # 404 e não 403: para quem está fora da máquina, esta rota não existe.
        # Um 403 confirmaria o endereço e o nome do endpoint.
        raise HTTPException(status_code=404, detail="Not Found")


def _recusar_navegador(request: Request) -> None:
    if request.headers.get("origin"):
        raise HTTPException(status_code=404, detail="Not Found")


@router.post("/bridge/eventos", status_code=202)
async def receber_evento(
    request: Request,
    x_controlfawkes_bridge: str | None = Header(default=None),
) -> dict:
    """Um evento de mídia do Native Host.

    A resposta nunca diz QUAL tranca falhou por credencial: ausente e errada
    dão a mesma resposta, porque distinguir as duas conta a quem tenta que o
    caminho está certo e falta só o segredo.
    """
    _exigir_loopback(request)
    _recusar_navegador(request)

    if not credencial.confere(x_controlfawkes_bridge):
        # Sem detalhe e sem eco do que veio: o segredo apresentado não volta na
        # resposta nem entra em log nenhum.
        raise HTTPException(status_code=401, detail="Credencial da ponte inválida.")

    try:
        corpo = await request.json()
    except Exception:  # noqa: BLE001 - corpo ilegível é entrada inválida
        raise HTTPException(status_code=400, detail="Corpo não é JSON.") from None

    resultado = validar(corpo, time.time())
    if isinstance(resultado, Recusa):
        raise HTTPException(
            status_code=422,
            detail={"code": resultado.code, "detail": resultado.detail},
        )

    # Aceito, e nada além disso. Quem transforma evento em sessão é o Merger, e
    # ele entra por aqui na Fase 8, quando houver frescor para alimentá-lo. Uma
    # rota que já mexesse no histórico seria a Fase 12 acontecendo por acidente.
    return {
        "ok": True,
        "accepted": resultado.messageType,
        "sessionId": resultado.sessionId,
    }
