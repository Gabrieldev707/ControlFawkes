"""Instala (ou remove) o native host do ControlFawkes no Chrome e no Edge.

Este script É a medição de custo de instalação que a Fase 1 pede. Tudo o que
ele faz é o que qualquer usuário teria de fazer para o Native Messaging
funcionar — e a extensão do custo é o argumento contra ou a favor do
transporte.

O que precisa estar certo, e o que quebra quando não está:

    manifesto do host   um JSON com nome, caminho e allowed_origins
    caminho ABSOLUTO    caminho relativo é silenciosamente ignorado
    chave no registro   HKCU\\Software\\Google\\Chrome\\NativeMessagingHosts\\<nome>
    ID da extensão      tem de bater com o do manifest.json, ou o Chrome recusa

O registro fica em HKCU e não em HKLM: não exige administrador, e some com
`--remover`. Nada aqui toca em máquina de outro usuário.

Uso:
    .venv\\Scripts\\python.exe scripts/instalar_native_host.py
    .venv\\Scripts\\python.exe scripts/instalar_native_host.py --remover
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


NOME_DO_HOST = "com.controlfawkes.bridge"

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
RAIZ_REPO = RAIZ_BACKEND.parent
IDENTIDADE = RAIZ_BACKEND / "data" / "bridge" / "identidade.json"
MANIFESTO_DA_EXTENSAO = RAIZ_REPO / "browser-extension" / "manifest.json"
LANCADOR = RAIZ_BACKEND / "scripts" / "controlfawkes_native_host.bat"
MANIFESTO_DO_HOST = RAIZ_BACKEND / "data" / "bridge" / f"{NOME_DO_HOST}.json"

# Chrome e Edge leem do mesmo formato, em ramos diferentes do registro.
RAMOS = {
    "Chrome": r"Software\Google\Chrome\NativeMessagingHosts",
    "Edge": r"Software\Microsoft\Edge\NativeMessagingHosts",
}


class Incoerente(RuntimeError):
    """Alguma peça da identidade não bate com outra."""


def _identidade() -> dict:
    if not IDENTIDADE.exists():
        raise Incoerente(
            f"Identidade ausente: {IDENTIDADE}\n"
            "Rode antes: scripts/gerar_identidade_da_extensao.py",
        )
    return json.loads(IDENTIDADE.read_text(encoding="utf-8"))


def _conferir_o_manifesto_da_extensao(identidade: dict) -> None:
    """A `key` do manifest.json e a identidade têm de ser a mesma chave.

    Se divergirem, o Chrome calcula um ID diferente do que está em
    `allowed_origins` e recusa a conexão — sem erro na extensão, sem erro no
    host, sem nada no log. Falhar aqui, alto, custa muito menos do que
    descobrir isso depois.
    """
    if not MANIFESTO_DA_EXTENSAO.exists():
        raise Incoerente(f"manifest.json da extensão não encontrado: {MANIFESTO_DA_EXTENSAO}")
    manifesto = json.loads(MANIFESTO_DA_EXTENSAO.read_text(encoding="utf-8"))
    if manifesto.get("key") != identidade["manifestKey"]:
        raise Incoerente(
            "A `key` do browser-extension/manifest.json NÃO é a mesma de "
            f"{IDENTIDADE}.\nO Chrome derivaria outro ID e recusaria a conexão.",
        )


def escrever_manifesto_do_host(identidade: dict) -> Path:
    MANIFESTO_DO_HOST.parent.mkdir(parents=True, exist_ok=True)
    conteudo = {
        "name": NOME_DO_HOST,
        "description": "ControlFawkes Browser Media Bridge",
        # Absoluto: caminho relativo é ignorado em silêncio pelo Chrome.
        "path": str(LANCADOR),
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{identidade['extensionId']}/"],
    }
    MANIFESTO_DO_HOST.write_text(
        json.dumps(conteudo, indent=2) + "\n", encoding="utf-8",
    )
    return MANIFESTO_DO_HOST


def registrar(remover: bool = False) -> list[str]:
    if sys.platform != "win32":
        return ["registro pulado: não é Windows"]

    import winreg

    feitos = []
    for navegador, ramo in RAMOS.items():
        caminho = f"{ramo}\\{NOME_DO_HOST}"
        if remover:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, caminho)
                feitos.append(f"{navegador}: chave removida")
            except FileNotFoundError:
                feitos.append(f"{navegador}: nada a remover")
            continue

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, caminho) as chave:
            # O valor padrão da chave é o caminho do manifesto do host.
            winreg.SetValueEx(chave, None, 0, winreg.REG_SZ, str(MANIFESTO_DO_HOST))
        feitos.append(f"{navegador}: HKCU\\{caminho}")
    return feitos


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remover", action="store_true", help="desinstala")
    argumentos = parser.parse_args()

    try:
        identidade = _identidade()
        if not argumentos.remover:
            _conferir_o_manifesto_da_extensao(identidade)
    except Incoerente as erro:
        print(f"ERRO: {erro}")
        return 1

    if argumentos.remover:
        for linha in registrar(remover=True):
            print(f"  {linha}")
        MANIFESTO_DO_HOST.unlink(missing_ok=True)
        print("Native host removido.")
        return 0

    if not LANCADOR.exists():
        print(f"ERRO: lançador ausente: {LANCADOR}")
        return 1

    destino = escrever_manifesto_do_host(identidade)
    print(f"extensionId : {identidade['extensionId']}")
    print(f"manifesto   : {destino}")
    print(f"lancador    : {LANCADOR}")
    for linha in registrar():
        print(f"  {linha}")
    print()
    print("Falta o passo MANUAL, que nenhum script pode fazer por voce:")
    print("  1. abrir chrome://extensions")
    print("  2. ligar o Modo do desenvolvedor")
    print("  3. 'Carregar sem compactacao' e escolher:")
    print(f"     {RAIZ_REPO / 'browser-extension'}")
    print(f"  4. conferir que o ID mostrado e {identidade['extensionId']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
