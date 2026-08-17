"""O nome e a foto de quem usa o controle — agora no computador.

Não confundir com `profiles/store.py`: aquele guarda os perfis DO SERVIÇO, os
avatares de "quem está assistindo?" da Netflix e do Max, com as coordenadas de
onde clicar. Este é sobre a pessoa.

## Por que saiu do navegador

Estava em `localStorage`, por uma decisão deliberada e defensável: a foto é
recortada no próprio celular, nunca subia para lugar nenhum, e o controle não
guardava nada sobre a pessoa — só sobre o computador.

O preço apareceu em 17/08/2026. O controle era aberto em `192.168.0.168:5174`,
passou a ser aberto em `:5173`, e nome e foto sumiram. `localStorage` é
separado por ORIGEM, e origem inclui a porta: são dois armazenamentos
diferentes, e o segundo nasce vazio. Nada tinha sido apagado — o dado estava em
outra gaveta, inalcançável.

E o mesmo aconteceria em cada troca de celular, cada navegador diferente, cada
aba anônima. Um dado que a pessoa entende como "minha conta" não pode depender
da porta em que o servidor de desenvolvimento subiu naquele dia.

## O que muda, e o que não muda

A foto passa a ser gravada em `backend/data/`. Isso é uma mudança real de
propriedade e ela merece ser dita em voz alta: a imagem sai do celular. O que
ela NÃO faz é sair da casa — o destino é o mesmo computador que já está sendo
controlado, na mesma rede local, no mesmo diretório que o Git ignora e que o
botão "apagar histórico" alcança. Não há serviço externo, conta ou nuvem
envolvidos, e continua não havendo login.

Quem quiser o comportamento antigo tem o botão de remover, que apaga dos dois
lados.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os


ARQUIVO_PADRAO = Path(__file__).resolve().parent.parent.parent / "data" / "perfil.json"

# Um nome, não um texto. Longo demais é sempre engano ou abuso, e ele vai para a
# tela sem rolagem.
MAXIMO_DO_NOME = 60

# A foto chega como `data:` URI de um JPEG 256×256 — perto de 20 KB em base64.
# Meio megabyte é folga larga para variação de qualidade e ainda barra alguém
# tentando usar o perfil como armazenamento de arquivo.
MAXIMO_DA_FOTO = 512 * 1024

# Só imagem, e só embutida. Uma URL externa aqui viraria uma requisição que o
# celular faria para fora da rede sem ninguém ter pedido.
PREFIXOS_DE_FOTO = ("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")


@dataclass(frozen=True)
class Perfil:
    nome: str | None = None
    foto: str | None = None

    def como_dicionario(self) -> dict:
        return {"nome": self.nome, "foto": self.foto}


class PerfilDoUsuario:
    def __init__(self, caminho: Path | None = None) -> None:
        self._caminho = caminho or ARQUIVO_PADRAO

    def ler(self) -> Perfil:
        """O perfil guardado. Vazio quando não há, nunca erro.

        Um arquivo estragado devolve perfil vazio em vez de derrubar a tela:
        o perfil é enfeite, e a pessoa pode preencher de novo.
        """
        try:
            dados = json.loads(self._caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return Perfil()
        if not isinstance(dados, dict):
            return Perfil()
        return Perfil(nome=_nome_valido(dados.get("nome")), foto=_foto_valida(dados.get("foto")))

    def salvar(self, nome: object, foto: object) -> Perfil:
        """Guarda o que veio, limpo. Devolve o que ficou guardado.

        Devolve em vez de só confirmar porque o que entra pode não ser o que
        fica: um nome com espaço em volta é aparado, e uma foto que não passa na
        validação vira ausente. A tela precisa saber o resultado real, senão ela
        mostra o que mandou e o servidor guardou outra coisa.
        """
        perfil = Perfil(nome=_nome_valido(nome), foto=_foto_valida(foto))
        self._gravar(perfil)
        return perfil

    def _gravar(self, perfil: Perfil) -> bool:
        try:
            self._caminho.parent.mkdir(parents=True, exist_ok=True)
            temporario = self._caminho.with_suffix(".tmp")
            temporario.write_text(
                json.dumps(perfil.como_dicionario(), ensure_ascii=False), encoding="utf-8",
            )
            # Troca atômica: um desligamento no meio da escrita apagaria tudo.
            os.replace(temporario, self._caminho)
        except OSError:
            return False
        return True

    def limpar(self) -> bool:
        try:
            self._caminho.unlink(missing_ok=True)
        except OSError:
            return False
        return True


def _nome_valido(valor: object) -> str | None:
    if not isinstance(valor, str):
        return None
    limpo = " ".join(valor.split())
    return limpo[:MAXIMO_DO_NOME] or None


def _foto_valida(valor: object) -> str | None:
    if not isinstance(valor, str) or not valor:
        return None
    if not valor.startswith(PREFIXOS_DE_FOTO):
        return None
    if len(valor) > MAXIMO_DA_FOTO:
        return None
    return valor
