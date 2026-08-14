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


def responder(mensagem: dict, sonda: Callable[[], dict] | None = None) -> dict:
    """A resposta para uma mensagem da extensão.

    Função pura em cima de uma sonda injetável: é o que permite provar o
    caminho inteiro sem Chrome, sem registro do Windows e sem servidor no ar.
    """
    sonda = sonda or _sonda_padrao

    versao = mensagem.get("protocolVersion")
    if versao != PROTOCOL_VERSION:
        return _erro(
            "PROTOCOL_VERSION_MISMATCH",
            f"Esperava protocolVersion {PROTOCOL_VERSION}, veio {versao!r}.",
        )

    tipo = mensagem.get("messageType")
    if tipo != "PING":
        # Fase 6: os eventos de mídia passam pela validação e viram ACK. O host
        # continua sendo relay — ele não interpreta o que o evento SIGNIFICA,
        # só confere que é utilizável antes de deixar entrar.
        from app.bridge.eventos import Recusa, validar

        resultado = validar(mensagem, time.time())
        if isinstance(resultado, Recusa):
            anotar("RECUSADA", f"{resultado.code} {resultado.detail}")
            return _erro(resultado.code, resultado.detail)
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
    from pathlib import Path

    if os.environ.get(VARIAVEL_SEM_LOG, "").strip() not in ("", "0"):
        return

    caminho = Path(__file__).resolve().parent.parent.parent / "data" / "bridge" / "host.log"
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
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


def _temporais(mensagem: dict) -> str:
    payload = mensagem.get("payload")
    if not isinstance(payload, dict):
        return ""
    partes = [
        f"{campo}={payload[campo]}"
        for campo in _CAMPOS_TEMPORAIS
        if campo in payload
    ]
    return " ".join(partes)


def servir(entrada, saida, sonda: Callable[[], dict] | None = None) -> None:
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
            escrever_mensagem(saida, _erro("INVALID_MESSAGE", str(erro)))
            continue

        anotar("RECEBIDA", f"{mensagem.get('messageType')} {_temporais(mensagem)}")
        escrever_mensagem(saida, responder(mensagem, sonda))


def main() -> int:  # pragma: no cover - o ponto de entrada real
    from app.bridge.framing import preparar_streams_binarios

    entrada, saida = preparar_streams_binarios()
    anotar("HOST_INICIADO")
    try:
        servir(entrada, saida)
        anotar("HOST_ENCERRADO", "cano fechado pelo Chrome")
    except Exception as erro:  # noqa: BLE001
        anotar("HOST_CRASH", repr(erro))
        # Última rede: o host não pode morrer com traceback no stdout, porque
        # stdout É o canal. O traceback viraria lixo no meio do enquadramento.
        try:
            escrever_mensagem(saida, _erro("HOST_CRASH", repr(erro)))
        except Exception:  # noqa: BLE001
            pass
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys as _sys

    _sys.exit(main())
