"""O enquadramento que o Chrome usa para falar com um native host.

O protocolo é curto e não negocia nada: cada mensagem é um inteiro de 4 bytes
com o tamanho, seguido do JSON em UTF-8. O tamanho vai na ordem de bytes NATIVA
da máquina — não em rede. No Windows isso é little-endian, e é por isso que o
`struct` aqui usa `@I` e não `!I`: trocar por rede funcionaria em teste e
devolveria lixo em produção, porque quem escreve do outro lado é o Chrome.

Limites do Chrome, e a razão de cada um estar aqui:

    1 MB    do Chrome para o host. Acima disso o Chrome nem envia.
    64 MB   do host para o Chrome. Acima disso o Chrome derruba a conexão.

Recusar aqui, e não lá, é o que transforma "a ponte morreu sem dizer nada" em
um erro com nome. E vale a regra que o Master Loop escreveu: a extensão não é
tratada como fonte confiável só porque é nossa.

Um detalhe que só aparece em produção: no Windows o stdio precisa estar em modo
binário. Em modo texto o Python traduz `\n` para `\r\n` na saída, e um único
`0x0A` dentro do cabeçalho de tamanho vira dois bytes — o Chrome lê um tamanho
errado e a conexão morre calada. Ver `preparar_streams_binarios`.
"""

from __future__ import annotations

import json
import struct
import sys


# `@` é o tamanho e a ordem nativos da máquina, que é o que o Chrome usa.
_CABECALHO = struct.Struct("@I")
TAMANHO_DO_CABECALHO = _CABECALHO.size

# Do Chrome para o host.
MAXIMO_DE_ENTRADA = 1024 * 1024
# Do host para o Chrome.
MAXIMO_DE_SAIDA = 64 * 1024 * 1024


class PonteFechada(Exception):
    """O outro lado fechou o cano. É o fim normal, não um defeito."""


class MensagemInvalida(Exception):
    """Veio alguma coisa que não é uma mensagem utilizável."""


def _ler_exatamente(stream, quantidade: int) -> bytes:
    """Lê `quantidade` bytes, ou levanta.

    `read()` pode devolver menos do que se pediu — em cano, quase sempre
    devolve. Um `read(n)` solto funciona no teste, onde tudo já está no buffer,
    e trunca a mensagem em produção.
    """
    partes: list[bytes] = []
    faltando = quantidade
    while faltando > 0:
        pedaco = stream.read(faltando)
        if not pedaco:
            if not partes:
                raise PonteFechada
            raise MensagemInvalida(
                f"Mensagem truncada: esperava {quantidade} bytes, vieram "
                f"{quantidade - faltando}.",
            )
        partes.append(pedaco)
        faltando -= len(pedaco)
    return b"".join(partes)


def ler_mensagem(stream) -> dict:
    """A próxima mensagem vinda do Chrome.

    Levanta `PonteFechada` quando o cano acaba de forma limpa — que é como o
    Chrome avisa que a porta foi fechada, o service worker morreu ou o
    navegador saiu.
    """
    cabecalho = _ler_exatamente(stream, TAMANHO_DO_CABECALHO)
    (tamanho,) = _CABECALHO.unpack(cabecalho)

    if tamanho == 0:
        raise MensagemInvalida("Mensagem de tamanho zero.")
    # Antes de alocar, e não depois: um tamanho absurdo é justamente o que não
    # se deve reservar memória para descobrir.
    if tamanho > MAXIMO_DE_ENTRADA:
        raise MensagemInvalida(
            f"Mensagem de {tamanho} bytes acima do limite de {MAXIMO_DE_ENTRADA}.",
        )

    bruto = _ler_exatamente(stream, tamanho)
    try:
        conteudo = json.loads(bruto.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as erro:
        raise MensagemInvalida(f"Conteúdo não é JSON válido: {erro}") from erro

    # Objeto e não lista: o envelope tem campos com nome, e aceitar uma lista
    # aqui empurraria o erro para dentro de quem consome.
    if not isinstance(conteudo, dict):
        raise MensagemInvalida("A mensagem precisa ser um objeto JSON.")
    return conteudo


def escrever_mensagem(stream, conteudo: dict) -> None:
    """Manda uma mensagem para o Chrome e garante que ela saiu.

    O `flush` não é zelo: sem ele a resposta fica no buffer do Python e o
    Chrome espera para sempre por algo que já foi escrito.
    """
    bruto = json.dumps(conteudo, ensure_ascii=False).encode("utf-8")
    if len(bruto) > MAXIMO_DE_SAIDA:
        raise MensagemInvalida(
            f"Resposta de {len(bruto)} bytes acima do limite de {MAXIMO_DE_SAIDA}.",
        )
    stream.write(_CABECALHO.pack(len(bruto)))
    stream.write(bruto)
    stream.flush()


def preparar_streams_binarios() -> tuple:
    """Os canos crus do processo, sem tradução de texto.

    `sys.stdin.buffer` e `sys.stdout.buffer` já são binários. O que ainda falta
    no Windows é desligar a tradução no nível do descritor: sem
    `O_BINARY`, um `0x0A` dentro do cabeçalho de tamanho vira `0x0D 0x0A` e o
    Chrome lê um tamanho que não existe.
    """
    if sys.platform == "win32":  # pragma: no cover - depende do sistema
        import msvcrt
        import os

        for stream in (sys.stdin, sys.stdout):
            msvcrt.setmode(stream.fileno(), os.O_BINARY)
    return sys.stdin.buffer, sys.stdout.buffer
