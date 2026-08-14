"""Os perfis de cada serviço, como o controle os conhece.

O que fica guardado é o mínimo para reproduzir um toque: um nome, onde tocar
dentro da janela, e o recorte da imagem que estava ali. Nada de login, nada de
sessão — o controle não sabe nem quer saber quem é o dono do perfil na Netflix.

Por plataforma porque é assim que a vida é: os perfis da Netflix não existem no
Disney+, e a posição de um não diz nada sobre o outro.

Fica em `backend/data/`, a mesma pasta ignorada pelo Git onde já moram o
pareamento e a chave do catálogo. O avatar vai embutido em base64: são poucos
kilobytes por perfil e evita espalhar arquivo solto no disco.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.schemas.ws import Platform


ARQUIVO_PADRAO = Path(__file__).resolve().parent.parent.parent / "data" / "perfis.json"

# Teto por plataforma. A Netflix permite cinco; a folga cobre os outros
# serviços sem deixar o arquivo virar depósito.
MAXIMO_POR_PLATAFORMA = 8

TAMANHO_MAXIMO_DO_AVATAR = 256 * 1024


@dataclass(frozen=True)
class Perfil:
    id: str
    nome: str
    x: float
    y: float
    avatar: bytes | None

    def sem_avatar(self) -> dict:
        """A forma que vai para o celular: a imagem tem endereço próprio."""
        return {"id": self.id, "nome": self.nome, "temAvatar": self.avatar is not None}


class ProfileStore:
    def __init__(self, caminho: Path | None = None) -> None:
        self._caminho = caminho or ARQUIVO_PADRAO

    def _ler(self) -> dict[str, list[dict]]:
        try:
            dados = json.loads(self._caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Sem arquivo ou corrompido: nenhum perfil cadastrado, que é um
            # estado normal e não um erro.
            return {}
        return dados if isinstance(dados, dict) else {}

    def _gravar(self, dados: dict[str, list[dict]]) -> bool:
        try:
            self._caminho.parent.mkdir(parents=True, exist_ok=True)
            temporario = self._caminho.with_suffix(".tmp")
            temporario.write_text(
                json.dumps(dados, ensure_ascii=False), encoding="utf-8",
            )
            # Troca atômica: um desligamento no meio da escrita deixaria um
            # arquivo pela metade, e aí todos os perfis sumiriam de uma vez.
            os.replace(temporario, self._caminho)
        except OSError:
            return False
        return True

    @staticmethod
    def _do_dicionario(bruto: object) -> Perfil | None:
        if not isinstance(bruto, dict):
            return None
        identificador = bruto.get("id")
        nome = bruto.get("nome")
        x, y = bruto.get("x"), bruto.get("y")
        if not isinstance(identificador, str) or not isinstance(nome, str):
            return None
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return None
        avatar = None
        codificado = bruto.get("avatar")
        if isinstance(codificado, str) and codificado:
            try:
                avatar = base64.b64decode(codificado, validate=True)
            except ValueError:
                avatar = None
        return Perfil(identificador, nome, float(x), float(y), avatar)

    def listar(self, platform: Platform) -> list[Perfil]:
        crus = self._ler().get(platform, [])
        if not isinstance(crus, list):
            return []
        perfis = (self._do_dicionario(item) for item in crus)
        return [perfil for perfil in perfis if perfil is not None]

    def tudo(self) -> dict[str, list[Perfil]]:
        return {
            plataforma: self.listar(plataforma)  # type: ignore[arg-type]
            for plataforma in self._ler()
        }

    def buscar(self, platform: Platform, profile_id: str) -> Perfil | None:
        return next((p for p in self.listar(platform) if p.id == profile_id), None)

    def adicionar(
        self, platform: Platform, nome: str, x: float, y: float, avatar: bytes | None,
    ) -> Perfil | None:
        nome_limpo = nome.strip()[:40]
        if not nome_limpo:
            return None
        if avatar is not None and len(avatar) > TAMANHO_MAXIMO_DO_AVATAR:
            avatar = None

        dados = self._ler()
        atuais = dados.get(platform)
        if not isinstance(atuais, list):
            atuais = []
        if len(atuais) >= MAXIMO_POR_PLATAFORMA:
            return None

        perfil = Perfil(uuid.uuid4().hex, nome_limpo, float(x), float(y), avatar)
        atuais.append({
            "id": perfil.id,
            "nome": perfil.nome,
            "x": perfil.x,
            "y": perfil.y,
            "avatar": base64.b64encode(avatar).decode("ascii") if avatar else None,
        })
        dados[platform] = atuais
        return perfil if self._gravar(dados) else None

    def remover(self, platform: Platform, profile_id: str) -> bool:
        dados = self._ler()
        atuais = dados.get(platform)
        if not isinstance(atuais, list):
            return False
        restantes = [
            item for item in atuais
            if not (isinstance(item, dict) and item.get("id") == profile_id)
        ]
        if len(restantes) == len(atuais):
            return False
        if restantes:
            dados[platform] = restantes
        else:
            dados.pop(platform, None)
        return self._gravar(dados)

    def limpar(self) -> bool:
        try:
            self._caminho.unlink(missing_ok=True)
        except OSError:
            return False
        return True
