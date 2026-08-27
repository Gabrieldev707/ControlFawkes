"""Onde a chave do catálogo fica guardada.

A variável de ambiente continua valendo e tem prioridade: quem já configurou
assim não precisa mudar nada, e num servidor de verdade é como se faz. O
arquivo existe para o caso doméstico — colar a chave pelo celular e o catálogo
passar a funcionar, sem editar variável nem reiniciar o servidor.

Fica em `backend/data/`, pasta ignorada pelo Git, junto do resto do estado
local. A chave do TMDB é de leitura de catálogo público: não dá acesso a conta
nem a dado pessoal.
"""

from __future__ import annotations

import json
from pathlib import Path


ARQUIVO_PADRAO = Path(__file__).resolve().parent.parent.parent / "data" / "tmdb.json"


class TmdbKeyStore:
    def __init__(self, caminho: Path | None = None) -> None:
        self._caminho = caminho or ARQUIVO_PADRAO

    def load(self) -> str:
        try:
            dados = json.loads(self._caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Sem arquivo, ilegível ou corrompido: o catálogo simplesmente fica
            # desligado, que é um estado previsto e não um erro.
            return ""
        chave = dados.get("apiKey") if isinstance(dados, dict) else None
        return chave.strip() if isinstance(chave, str) else ""

    def save(self, chave: str) -> bool:
        try:
            self._caminho.parent.mkdir(parents=True, exist_ok=True)
            self._caminho.write_text(
                json.dumps({"apiKey": chave.strip()}, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            return False
        return True

    def clear(self) -> bool:
        try:
            self._caminho.unlink(missing_ok=True)
        except OSError:
            return False
        return True
