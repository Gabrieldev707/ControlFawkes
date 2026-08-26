"""O host que o Chrome inicia — e que NÃO é o ControlFawkes.

Este é o ponto que o plano V1 desenhava errado e a V1.1 corrigiu. Native
Messaging funciona assim: o Chrome SPAWNA o executável do host como processo
filho e fala com ele por stdio. O ControlFawkes já está rodando — servidor
FastAPI de longa duração, com trava de instância exclusiva. O Chrome não vai
spawnar ele.

Logo, o salto local que o Native Messaging supostamente evitava continua
existindo:

    Extensão → (stdio) → este host → (HTTP local) → ControlFawkes

A diferença real não é "menos um salto". É QUEM PODE ABRIR O PRIMEIRO CANAL: o
Chrome só entrega stdio a um host declarado, e só a partir de uma extensão cujo
ID está em `allowed_origins`. Uma página web qualquer não alcança isso. Já um
WebSocket em localhost é alcançável por qualquer página aberta no navegador.

O que este arquivo NÃO pode ganhar, nunca:

    Media Merger, adapters, lógica de Netflix, histórico, relógio, regras de
    sessão.

É um relay. Um relay com lógica de domínio vira um segundo ControlFawkes — que
é exatamente o critério de implementação incorreta nº 11 do Master Loop.
"""

from __future__ import annotations

from collections.abc import Callable
import json
import threading
import time

from app.bridge.framing import (
    MensagemInvalida,
    PonteFechada,
    ler_mensagem,
    escrever_mensagem,
)


PROTOCOL_VERSION = 1

# Endereço do ControlFawkes já em execução. Localhost e não o IP da LAN: o host
# roda na mesma máquina, e sair para a rede seria dar um alcance que ele não
# precisa ter.
CONTROLFAWKES_BASE = "http://127.0.0.1:8100"

# Curto de propósito. O host está no caminho de uma mensagem que o Chrome está
# esperando; melhor responder "não alcancei" do que pendurar a porta.
TIMEOUT_SEGUNDOS = 3.0


# O stdout do host passou a ter DUAS bocas na Fase 16.
#
# Antes, só o laço de `servir()` escrevia: uma mensagem entrava, uma resposta
# saía, em ordem. Agora o laço de comandos escreve também, de outra thread, e
# stdout É o canal do Native Messaging — duas escritas entrelaçadas desalinham
# o enquadramento e derrubam a conexão sem nenhuma mensagem de erro.
#
# É o mesmo cuidado que faz `anotar` gravar em arquivo e nunca em stdout, um
# nível abaixo.
_TRAVA_DA_SAIDA = threading.Lock()


def _escrever(saida, mensagem: dict) -> None:
    """Uma escrita por vez. Ver `_TRAVA_DA_SAIDA`."""
    with _TRAVA_DA_SAIDA:
        escrever_mensagem(saida, mensagem)


def _sonda_padrao() -> dict:
    """Alcança o ControlFawkes e devolve o que ele responde.

    `/health` de propósito: a Fase 1 decide TRANSPORTE, não protocolo. Inventar
    um endpoint de ingestão aqui seria fazer trabalho da Fase 6 com um contrato
    que ainda não existe — e depois ter de desfazer.
    """
    import httpx

    resposta = httpx.get(f"{CONTROLFAWKES_BASE}/health", timeout=TIMEOUT_SEGUNDOS)
    resposta.raise_for_status()
    return resposta.json()


def _entrega_padrao(mensagem: dict) -> dict:
    """Entrega o evento na rota interna do ControlFawkes, autenticado.

    O segredo é lido do disco a cada entrega e NÃO é guardado em atributo nem
    passado adiante. Ele existe entre a leitura e o cabeçalho, e some.
    """
    import httpx

    from app.bridge.credencial import CABECALHO, CredencialDaPonte

    segredo = CredencialDaPonte().ler()
    if segredo is None:
        # O servidor gera a credencial ao subir. Sem arquivo, ou o ControlFawkes
        # nunca rodou nesta máquina, ou alguém apagou — e o host NÃO gera uma
        # por conta própria: duas credenciais diferentes é pior do que nenhuma.
        raise RuntimeError("credencial da ponte ausente")

    resposta = httpx.post(
        f"{CONTROLFAWKES_BASE}/bridge/eventos",
        json=mensagem,
        headers={CABECALHO: segredo},
        timeout=TIMEOUT_SEGUNDOS,
    )
    resposta.raise_for_status()
    return resposta.json()


def _resultado_padrao(payload: dict) -> None:
    """Devolve ao ControlFawkes o que a página respondeu. Fase 16."""
    import httpx

    from app.bridge.credencial import CABECALHO, CredencialDaPonte

    segredo = CredencialDaPonte().ler()
    if segredo is None:
        raise RuntimeError("credencial da ponte ausente")

    resposta = httpx.post(
        f"{CONTROLFAWKES_BASE}/bridge/comandos/{payload['id']}/resultado",
        json={"ok": payload.get("ok") is True, "detalhe": payload.get("detalhe")},
        headers={CABECALHO: segredo},
        timeout=TIMEOUT_SEGUNDOS,
    )
    resposta.raise_for_status()


#: Quanto o host espera antes de tentar de novo depois de uma falha de rede.
#:
#: Sem esta pausa, o ControlFawkes fora do ar viraria um laço apertado batendo
#: em porta fechada — milhares de tentativas por minuto, com o host consumindo
#: CPU para não conseguir nada. É o mesmo defeito que a enxurrada de
#: `ERR_BLOCKED_BY_CLIENT` do player do Max mostrou ao vivo em 26/08/2026:
#: cinquenta e três mil tentativas, sem limite nenhum.
SEGUNDOS_ANTES_DE_TENTAR_DE_NOVO = 5.0


def laco_de_comandos(saida, parar: threading.Event, buscar=None) -> None:
    """Pergunta ao ControlFawkes se há comando, e o escreve para a extensão.

    ## Por que é o host quem pergunta

    Native Messaging é o Chrome quem inicia: ele spawna o host e fala por
    stdio. Ninguém de fora abre uma conexão com o host — e é justamente essa a
    propriedade que fez a Fase 1 preferir este transporte a um WebSocket em
    localhost, que qualquer página aberta alcança.

    Manter a propriedade custa inverter a pergunta. O ControlFawkes não empurra;
    o host procura, e a rota SEGURA a resposta por até vinte e cinco segundos
    para o comando sair no instante em que a pessoa aperta o botão.

    ## Numa thread, e por quê

    O laço de `servir()` fica bloqueado lendo stdin — é assim que ele espera a
    próxima mensagem do Chrome. Uma consulta HTTP no meio dele atrasaria toda
    mensagem da extensão por até vinte e cinco segundos.

    As duas threads escrevem no MESMO stdout, que é o canal do Native
    Messaging, e duas escritas entrelaçadas desalinham o enquadramento. Quem
    resolve é `_TRAVA_DA_SAIDA`.

    ## O que ele NÃO faz

    Não interpreta o comando, não escolhe aba, não confere se a ação existe.
    Relay. Um relay com lógica de domínio vira um segundo ControlFawkes.
    """
    buscar = buscar or _buscar_comando
    while not parar.is_set():
        try:
            comando = buscar()
        except Exception as erro:  # noqa: BLE001 - servidor fora do ar é normal
            anotar("COMANDO_SEM_SERVIDOR", str(erro) or type(erro).__name__)
            # `wait` e não `sleep`: quando o cano fecha, o host tem de sair
            # agora, e não daqui a cinco segundos.
            parar.wait(SEGUNDOS_ANTES_DE_TENTAR_DE_NOVO)
            continue
        if comando is None:
            # Nenhum comando no período. É a resposta normal.
            continue
        anotar("COMANDO", comando.get("acao"))
        try:
            _escrever(saida, {
                "protocolVersion": PROTOCOL_VERSION,
                "messageType": "COMANDO",
                "payload": comando,
            })
        except Exception as erro:  # noqa: BLE001 - cano fechado encerra o laço
            anotar("COMANDO_NAO_ESCRITO", repr(erro))
            return


def _buscar_comando() -> dict | None:
    import httpx

    from app.bridge.credencial import CABECALHO, CredencialDaPonte

    segredo = CredencialDaPonte().ler()
    if segredo is None:
        raise RuntimeError("credencial da ponte ausente")

    resposta = httpx.get(
        f"{CONTROLFAWKES_BASE}/bridge/comandos",
        headers={CABECALHO: segredo},
        # Acima dos vinte e cinco segundos que a rota segura, senão o cliente
        # desiste sempre um instante antes de a resposta poder existir.
        timeout=35.0,
    )
    resposta.raise_for_status()
    return resposta.json().get("comando")


def responder(
    mensagem: dict,
    sonda: Callable[[], dict] | None = None,
    entregar: Callable[[dict], dict] | None = None,
    resultado_padrao: Callable[[dict], None] | None = None,
) -> dict:
    """A resposta para uma mensagem da extensão.

    Função pura em cima de uma sonda e de uma entrega injetáveis: é o que
    permite provar o caminho inteiro sem Chrome, sem registro do Windows e sem
    servidor no ar.
    """
    sonda = sonda or _sonda_padrao
    entregar = entregar or _entrega_padrao

    versao = mensagem.get("protocolVersion")
    if versao != PROTOCOL_VERSION:
        return _erro(
            "PROTOCOL_VERSION_MISMATCH",
            f"Esperava protocolVersion {PROTOCOL_VERSION}, veio {versao!r}.",
        )

    tipo = mensagem.get("messageType")
    if tipo == "RESULTADO":
        # Fase 16 — a página executou o comando (ou não). Sobe pelo mesmo cano
        # e vai para a rota de resultado, não para a de eventos: um resultado
        # não é um evento de mídia e não tem `sessionId` nem tempo.
        #
        # O host continua sendo relay: ele não olha se o comando fazia sentido
        # nem o que ele significava. Só repassa.
        payload = mensagem.get("payload")
        if not isinstance(payload, dict) or not isinstance(payload.get("id"), str):
            return _erro("INVALID_MESSAGE", "RESULTADO sem id.")
        try:
            (resultado_padrao or _resultado_padrao)(payload)
        except Exception as erro:  # noqa: BLE001 - toda falha de entrega é a mesma
            return _erro("CONTROLFAWKES_UNREACHABLE", str(erro) or type(erro).__name__)
        return {"protocolVersion": PROTOCOL_VERSION, "messageType": "ACK", "ok": True}

    if tipo != "PING":
        # Fase 6: os eventos de mídia passam pela validação e viram ACK. O host
        # continua sendo relay — ele não interpreta o que o evento SIGNIFICA,
        # só confere que é utilizável antes de deixar entrar.
        from app.bridge.eventos import Recusa, validar

        resultado = validar(mensagem, time.time())
        if isinstance(resultado, Recusa):
            anotar("RECUSADA", f"{resultado.code} {resultado.detail}")
            return _erro(resultado.code, resultado.detail)

        # Valida ANTES de entregar. O host é relay, e um relay que repassa lixo
        # obriga o servidor a se defender sozinho de um cano que ele confia. E
        # não é redundância: a rota valida de novo, porque ela não pode supor
        # que quem bateu nela foi este host.
        try:
            entregar(mensagem)
        except Exception as erro:  # noqa: BLE001 - toda falha de entrega é a mesma
            # O ControlFawkes fora do ar é estado normal — o Chrome pode abrir
            # antes do servidor. A extensão precisa disso como dado.
            return _erro("CONTROLFAWKES_UNREACHABLE", str(erro) or type(erro).__name__)

        return {
            "protocolVersion": PROTOCOL_VERSION,
            "messageType": "ACK",
            "ok": True,
            "accepted": resultado.messageType,
        }

    try:
        saude = sonda()
    except Exception as erro:  # noqa: BLE001 - qualquer falha de rede é a mesma resposta
        # O ControlFawkes não estar no ar é estado NORMAL: o Chrome pode abrir
        # antes do servidor. A extensão precisa disso como dado, não como
        # silêncio.
        return _erro("CONTROLFAWKES_UNREACHABLE", str(erro) or type(erro).__name__)

    return {
        "protocolVersion": PROTOCOL_VERSION,
        "messageType": "PONG",
        "ok": True,
        "controlfawkes": saude,
    }


def _erro(codigo: str, detalhe: str) -> dict:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "messageType": "ERROR",
        "ok": False,
        "code": codigo,
        "detail": detalhe,
    }


# Desliga o log de diagnóstico. Existe para a suíte: os testes exercitam
# `servir()` de verdade, e sem isto cada execução despeja linhas no log da
# máquina — poluindo justamente o arquivo que serve para saber se o Chrome
# conectou. Medido: uma rodada de testes gravou cinco "RECEBIDA PING" que
# pareciam vir do navegador.
#
# Mesma forma da trava de instância: variável de ambiente, e não detecção de
# pytest dentro do código de produção. Quem desliga diz isso em voz alta.
VARIAVEL_SEM_LOG = "CONTROLFAWKES_BRIDGE_SEM_LOG"

#: Quando o log passa disto, ele vira `.log.anterior` e recomeca. Dois megas
#: sao semanas de uso e continuam abrindo instantaneamente num editor.
TAMANHO_MAXIMO_DO_LOG = 2_000_000


def caminho_do_log():
    """Onde o log vive. Função e não constante, para o teste poder trocar."""
    from pathlib import Path

    return Path(__file__).resolve().parent.parent.parent / "data" / "bridge" / "host.log"


def anotar(evento: str, detalhe: object = None) -> None:
    """Registra em ARQUIVO, nunca em stdout.

    stdout É o canal do Native Messaging: um `print` de diagnóstico desalinha o
    enquadramento e derruba a conexão sem nenhuma mensagem de erro. E stderr
    também não serve — o Chrome o captura e joga fora, então o que se escreve
    lá simplesmente some.

    Isto existe porque a falha mais comum do Native Messaging é silenciosa: a
    extensão vê "porta desconectada" e o host, quando chega a subir, morre sem
    deixar rastro. Com o arquivo, "não funcionou" vira uma linha com hora.
    """
    import os
    from datetime import datetime

    if os.environ.get(VARIAVEL_SEM_LOG, "").strip() not in ("", "0"):
        return

    caminho = caminho_do_log()
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        # Rotacao, porque este arquivo cresce para SEMPRE.
        #
        # Cada batimento de cada aba vira uma linha, e o batimento nao para
        # enquanto houver video aberto. Medido em 25/08/2026: 61.006 linhas,
        # 7,5 MB — e nada nunca apagava nada. Num computador que fica ligado,
        # isso nao tem fim.
        #
        # Uma geracao anterior e guardada: o diagnostico mais util costuma ser
        # "o que aconteceu ANTES de parar", e rotacionar sem guardar apagaria
        # justamente isso.
        if caminho.exists() and caminho.stat().st_size > TAMANHO_MAXIMO_DO_LOG:
            caminho.replace(caminho.with_suffix(".log.anterior"))
        with caminho.open("a", encoding="utf-8") as arquivo:
            arquivo.write(f"{datetime.now().isoformat(timespec='seconds')} {evento} {detalhe}\n")
    except OSError:
        # Diagnóstico nunca derruba a ponte.
        pass


# Os únicos campos do payload que vão para o log.
#
# A regra continua a mesma — não gravar navegação. O que mudou é a leitura de
# quais campos SÃO navegação: `href` e `provider` dizem onde a pessoa esteve;
# `currentTime` e `duration` dizem quanto tempo tem um vídeo, e isso não
# identifica nada. Sem eles a Fase 5 não tem como provar que o observador mede
# certo — o log diria que uma mensagem chegou, e não o que ela dizia.
_CAMPOS_TEMPORAIS = ("playbackState", "currentTime", "duration", "playbackRate")

# Campos cuja PRESENÇA é diagnóstico e cujo VALOR seria coleta.
#
# "O adapter da Netflix está funcionando?" é a pergunta que o log precisa
# responder, e ela se responde com sim/não. Gravar o nome da obra responderia a
# mesma pergunta e, de quebra, transformaria o log de diagnóstico num histórico
# do que a pessoa assistiu — que é a linha que este arquivo não cruza.
_CAMPOS_PRESENTES = ("workTitle", "episodeTitle", "seasonNumber", "pageId", "active")


def _temporais(mensagem: dict) -> str:
    payload = mensagem.get("payload")
    if not isinstance(payload, dict):
        return ""
    partes = [
        f"{campo}={payload[campo]}"
        for campo in _CAMPOS_TEMPORAIS
        if campo in payload
    ]
    presentes = [
        campo for campo in _CAMPOS_PRESENTES
        if payload.get(campo) is not None
    ]
    if presentes:
        partes.append(f"tem={'+'.join(presentes)}")
    return " ".join(partes)


def servir(
    entrada,
    saida,
    sonda: Callable[[], dict] | None = None,
    entregar: Callable[[dict], dict] | None = None,
) -> None:
    """O laço do host: uma mensagem entra, uma resposta sai.

    Termina quando o cano fecha — que é como o Chrome avisa que a porta caiu,
    o service worker morreu ou o navegador saiu. Isso é fim normal, e o host
    sai com código zero.

    Uma mensagem inválida NÃO derruba o laço. Derrubar entregaria à extensão o
    poder de matar o host com um byte errado, e o Chrome respawnaria em
    seguida — um ciclo de processos que ninguém veria.
    """
    while True:
        try:
            mensagem = ler_mensagem(entrada)
        except PonteFechada:
            return
        except MensagemInvalida as erro:
            anotar("MENSAGEM_INVALIDA", erro)
            _escrever(saida, _erro("INVALID_MESSAGE", str(erro)))
            continue

        anotar("RECEBIDA", f"{mensagem.get('messageType')} {_temporais(mensagem)}")
        _escrever(saida, responder(mensagem, sonda, entregar))


def main() -> int:  # pragma: no cover - o ponto de entrada real
    from app.bridge.framing import preparar_streams_binarios

    entrada, saida = preparar_streams_binarios()
    anotar("HOST_INICIADO")

    # Fase 16 — o sentido inverso. Uma thread daemon: quando o cano fecha, o
    # processo sai sem esperar por ela, e o `parar` é o pedido educado que ela
    # atende antes disso.
    parar = threading.Event()
    comandos = threading.Thread(
        target=laco_de_comandos, args=(saida, parar), daemon=True, name="comandos",
    )
    comandos.start()

    try:
        servir(entrada, saida)
        anotar("HOST_ENCERRADO", "cano fechado pelo Chrome")
    except Exception as erro:  # noqa: BLE001
        parar.set()
        anotar("HOST_CRASH", repr(erro))
        # Última rede: o host não pode morrer com traceback no stdout, porque
        # stdout É o canal. O traceback viraria lixo no meio do enquadramento.
        try:
            _escrever(saida, _erro("HOST_CRASH", repr(erro)))
        except Exception:  # noqa: BLE001
            pass
        return 1
    finally:
        parar.set()
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys as _sys

    _sys.exit(main())
