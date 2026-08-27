"""A ponte entre o id da obra NO PROVIDER e o id dela no TMDB.

`/watch/81043710` na Netflix e o ASIN no Prime identificam a obra dentro
daquele serviço com certeza absoluta — muito melhor do que qualquer casamento
de texto. Mas eles **não são** ids do TMDB, e não existe tabela pública ligando
os dois.

O que existe é isto: quando o resolver conseguir decidir com segurança que
`(netflix, 81043710)` é o TMDB 522627, essa descoberta fica guardada. Da
próxima vez não se refaz a busca por título — que é justamente a etapa frágil,
a que confunde "O Rei" de 2019 com o de 2014.

O sentido é de mão única de propósito: guardar só o que foi resolvido com
segurança. Uma associação errada gravada aqui é pior do que nenhuma, porque ela
vira identidade e passa a ganhar de todo o resto (`Nivel.PROVIDER_ID`). Por
isso `associar` só é chamado com resultado forte — ver `catalog/tmdb.py`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


ARQUIVO_PADRAO = (
    Path(__file__).resolve().parent.parent.parent / "data" / "identidades.json"
)

# Teto de associações guardadas. Cada uma é uma linha minúscula, mas um arquivo
# sem limite acaba grande por acúmulo e não por utilidade — o que interessa é o
# que se assiste, e isso é um conjunto pequeno.
MAXIMO = 500


def _chave(provider: str, content_id: str) -> str:
    return f"{provider.strip().lower()}::{content_id.strip()}"


class IdentidadeStore:
    def __init__(self, caminho: Path | None = None) -> None:
        self._caminho = caminho or ARQUIVO_PADRAO

    def _ler(self) -> dict[str, dict]:
        try:
            dados = json.loads(self._caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return dados if isinstance(dados, dict) else {}

    def tmdb_de(self, provider: str | None, content_id: str | None) -> int | None:
        """O id do TMDB já associado, se houver."""
        if not provider or not content_id:
            return None
        registro = self._ler().get(_chave(provider, content_id))
        if not isinstance(registro, dict):
            return None
        identificador = registro.get("tmdbId")
        return identificador if isinstance(identificador, int) else None

    def associar(
        self,
        provider: str | None,
        content_id: str | None,
        tmdb_id: int,
        tipo: str,
        titulo: str,
    ) -> bool:
        """Guarda uma associação que o resolver decidiu com segurança.

        Idempotente: reassociar o mesmo par não muda nada. Reassociar para um
        id DIFERENTE sobrescreve — o mais recente é o que a resolução mais
        informada decidiu, e manter o antigo congelaria um erro.
        """
        if not provider or not content_id:
            return False

        dados = self._ler()
        dados[_chave(provider, content_id)] = {
            "tmdbId": tmdb_id,
            "tipo": tipo,
            # Só para leitura humana do arquivo; nada depende dele.
            "titulo": titulo,
        }

        if len(dados) > MAXIMO:
            # Sem carimbo de tempo por item, o corte é pela ordem de inserção,
            # que o dict do Python preserva. As mais antigas saem.
            dados = dict(list(dados.items())[-MAXIMO:])

        try:
            self._caminho.parent.mkdir(parents=True, exist_ok=True)
            temporario = self._caminho.with_suffix(".tmp")
            temporario.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
            os.replace(temporario, self._caminho)
        except OSError:
            return False
        return True

    def esquecer(self, provider: str, content_id: str) -> bool:
        dados = self._ler()
        if dados.pop(_chave(provider, content_id), None) is None:
            return False
        try:
            self._caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        except OSError:
            return False
        return True
