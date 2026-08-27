"""Gera a identidade fixa da extensão — o par de chaves e o ID que dele sai.

Por que isto existe, e por que é a primeira coisa do Spike A:

O `allowed_origins` do manifesto do native host aponta para um ID de extensão
específico. Só que o ID de uma extensão CARREGADA DESCOMPACTADA é derivado do
CAMINHO da pasta — muda de máquina para máquina, e muda se a pasta for movida.
Com o ID mudando, o `allowed_origins` para de casar e o Chrome recusa a
conexão sem dizer por quê. É a pedra em que quase todo mundo tropeça.

A saída é fixar o campo `key` no `manifest.json`. Com ele presente, o Chrome
deriva o ID da CHAVE em vez do caminho, e o ID passa a ser o mesmo em qualquer
lugar.

Como o Chrome deriva o ID (não está bem documentado, mas é estável há anos):

    SHA-256 da chave pública em DER/SPKI
    → os 16 primeiros bytes
    → cada dígito hexadecimal vira uma letra, '0'→'a' ... 'f'→'p'

A chave privada só é necessária para empacotar um `.crx` depois. Ela é gravada
em `backend/data/`, que o Git ignora, e nunca precisa sair desta máquina.

Uso:
    .venv\\Scripts\\python.exe scripts/gerar_identidade_da_extensao.py
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


RAIZ = Path(__file__).resolve().parent.parent
DESTINO_PRIVADO = RAIZ / "data" / "bridge" / "extensao_privada.pem"
DESTINO_PUBLICO = RAIZ / "data" / "bridge" / "identidade.json"


def id_da_extensao(publica_der: bytes) -> str:
    """O ID que o Chrome vai calcular para esta chave."""
    digest = hashlib.sha256(publica_der).hexdigest()[:32]
    # '0'-'9' e 'a'-'f' viram 'a'-'p'. `int(c, 16)` cobre os dois casos.
    return "".join(chr(ord("a") + int(c, 16)) for c in digest)


def gerar() -> dict:
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    privada_pem = chave.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    publica_der = chave.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    DESTINO_PRIVADO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO_PRIVADO.write_bytes(privada_pem)

    identidade = {
        "extensionId": id_da_extensao(publica_der),
        # É este texto que vai no campo `key` do manifest.json.
        "manifestKey": base64.b64encode(publica_der).decode("ascii"),
    }
    DESTINO_PUBLICO.write_text(
        json.dumps(identidade, indent=2) + "\n", encoding="utf-8",
    )
    return identidade


if __name__ == "__main__":
    dados = gerar()
    print(f"extensionId : {dados['extensionId']}")
    print(f"manifestKey : {dados['manifestKey'][:48]}...")
    print()
    # ASCII puro: o console do Windows abre em cp1252 e uma seta derruba o
    # script DEPOIS de ele já ter gravado as chaves — o pior momento possível.
    print(f"privada  em {DESTINO_PRIVADO}")
    print(f"publica  em {DESTINO_PUBLICO}")
