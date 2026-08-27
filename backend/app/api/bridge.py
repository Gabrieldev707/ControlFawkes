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

from app.bridge.comandos import SEGUNDOS_DE_ESPERA, fila_de_comandos
from app.bridge.credencial import CABECALHO, CredencialDaPonte
from app.bridge.estado import estado_da_ponte
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


@router.get("/bridge/diagnostico")
async def diagnostico(request: Request) -> dict:
    """O que o servidor acha que está tocando, agora, e de onde tirou isso.

    Existe porque a alternativa é adivinhar. Três rodadas de depuração em
    25/08/2026 foram gastas inferindo estado de processo a partir de arquivos
    que não cresciam — o histórico parado dizia "algo está errado" e nunca
    dizia o quê.

    Mesmas trancas de `/bridge/eventos`, e pelo mesmo motivo: isto conta o que
    a pessoa está assistindo, e nenhuma página aberta no navegador pode
    alcançá-lo. Loopback e ausência de `Origin`. Sem credencial, porque não há
    o que escrever aqui e exigir o segredo só tornaria o diagnóstico mais
    difícil justamente quando ele é necessário.
    """
    _exigir_loopback(request)
    _recusar_navegador(request)

    from app.api import websocket as websocket_module
    from app.bridge.saude import SaudeDaSMTC, SaudeDoWindowTitle, smtc_disponivel

    dispatcher = websocket_module.dispatcher
    janela = dispatcher.window_focuser.media_window()

    return {
        "smtc": {
            **SaudeDaSMTC.de(dispatcher._leitura).__dict__,
            "disponivel": smtc_disponivel(),
        },
        "janela": {
            "titulo": janela.title if janela else None,
            "processo": janela.process if janela else None,
            **SaudeDoWindowTitle.de(janela.title if janela else None).__dict__,
        },
        "ponte": {
            **estado_da_ponte.saude().__dict__,
            "sessoes": [
                {
                    "platform": s.platform,
                    "playbackState": s.playbackState,
                    "currentTime": s.currentTime,
                    "duration": s.duration,
                    "sessionId": s.sessionId[:10],
                    "pageId": s.pageId,
                    "documentTitle": s.documentTitle,
                    "tabId": s.tabId,
                    "workTitle": s.workTitle,
                    "episodeTitle": s.episodeTitle,
                    "seasonNumber": s.seasonNumber,
                    "episodeNumber": s.episodeNumber,
                    "active": s.active,
                    "audible": s.audible,
                    # O tempo que veio da PÁGINA, separado do tempo do
                    # elemento. Sem os dois lado a lado, "a posição está
                    # errada" e "a âncora não foi criada" parecem a mesma
                    # coisa no diagnóstico — e são problemas diferentes.
                    "adapterPosition": s.adapterPosition,
                    "adapterDuration": s.adapterDuration,
                    # E onde a página diz que estão o vídeo e o botão de tela
                    # cheia. A presença deles também responde uma pergunta que
                    # eu vinha respondendo por dedução: o content script desta
                    # aba é o novo, ou é um órfão de antes de recarregar?
                    "videoCentro": (s.videoCentroX, s.videoCentroY),
                    "telaCheia": (s.telaCheiaX, s.telaCheiaY),
                }
                for s in estado_da_ponte.vivas()
            ],
        },
        # A leitura AGORA, e não a última transmitida. O laço só transmite
        # com celular conectado, então `_last_now_playing` fica nulo enquanto
        # ninguém está pareado — e um diagnóstico que responde "nada tocando"
        # porque ninguém está olhando é pior do que não existir.
        #
        # `contar=False`: consultar o diagnóstico não pode somar tempo assistido.
        "cartao": (await dispatcher._read_now_playing(contar=False)),
        "ultimo_transmitido": dispatcher._last_now_playing,
    }


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

    # Fase 8: o evento entra no estado vivo da ponte. Era aqui que ele morria —
    # a rota respondia `ok` e descartava, e o `currentTime` medido dentro da
    # página nunca chegava ao cartão nem ao histórico.
    #
    # A rota não INTERPRETA o evento: ela o entrega. Quem decide qual fonte
    # responde por qual campo continua sendo o Merger, e quem decide se aquilo
    # conta como assistido continua sendo a Fase 9. Uma rota que já mexesse no
    # histórico seria a Fase 12 acontecendo por acidente.
    estado_da_ponte.registrar(resultado)

    return {
        "ok": True,
        "accepted": resultado.messageType,
        "sessionId": resultado.sessionId,
    }


@router.get("/bridge/comandos")
async def proximo_comando(
    request: Request,
    x_controlfawkes_bridge: str | None = Header(default=None),
) -> dict:
    """O host pergunta se há comando para descer. Fase 16.

    Esta rota SEGURA a resposta por até vinte e cinco segundos. Não é lentidão:
    é o que faz um comando sair no instante em que a pessoa aperta o botão, em
    vez de esperar o próximo ciclo de consulta.

    Ela existe porque o host não pode ser chamado. Native Messaging é o Chrome
    quem inicia — ele spawna o host e fala por stdio, e ninguém de fora abre uma
    conexão com ele. Essa é a propriedade que fez a Fase 1 escolher este
    transporte em vez de um WebSocket em localhost, que qualquer página aberta
    alcança. Manter a propriedade custa inverter a pergunta: quem procura é o
    host.

    Mesmas três trancas de `/bridge/eventos` — loopback, sem `Origin`,
    credencial. E a credencial importa MAIS aqui do que na entrada: quem lê esta
    rota recebe o comando que ia para a aba, e poderia consumi-lo no lugar dela.
    """
    _exigir_loopback(request)
    _recusar_navegador(request)
    if not credencial.confere(x_controlfawkes_bridge):
        raise HTTPException(status_code=401, detail="Credencial da ponte inválida.")

    comando = await fila_de_comandos.proximo(SEGUNDOS_DE_ESPERA)
    if comando is None:
        # Silêncio é resposta normal: quase todo minuto não tem comando nenhum.
        return {"comando": None}
    return {"comando": comando.como_mensagem()["payload"]}


@router.post("/bridge/comandos/{id_do_comando}/resultado", status_code=202)
async def resultado_do_comando(
    id_do_comando: str,
    request: Request,
    x_controlfawkes_bridge: str | None = Header(default=None),
) -> dict:
    """A página executou (ou não). Fase 16.

    Chegar atrasado NÃO é erro: quem pediu espera um segundo e meio e depois
    cai para a tecla. Uma resposta que chega depois disso encontra a porta
    fechada, e a resposta desta rota diz isso em vez de fingir que deu certo.
    """
    _exigir_loopback(request)
    _recusar_navegador(request)
    if not credencial.confere(x_controlfawkes_bridge):
        raise HTTPException(status_code=401, detail="Credencial da ponte inválida.")

    try:
        corpo = await request.json()
    except Exception:  # noqa: BLE001 - corpo ilegível é entrada inválida
        raise HTTPException(status_code=400, detail="Corpo não é JSON.") from None
    if not isinstance(corpo, dict):
        raise HTTPException(status_code=400, detail="Corpo não é objeto.")

    ouvido = fila_de_comandos.resolver(
        id_do_comando,
        ok=corpo.get("ok") is True,
        detalhe=corpo.get("detalhe") if isinstance(corpo.get("detalhe"), str) else None,
    )
    return {"ok": True, "aguardado": ouvido}
