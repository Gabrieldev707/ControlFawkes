"""Conquistas, a partir do que já foi assistido.

Nada aqui é inventado nem pedido a lugar nenhum: cada medalha é uma pergunta
feita ao histórico local. Isso tem duas consequências boas — funciona com o
catálogo desligado (menos as que dependem de gênero) e some junto quando a
pessoa apaga o histórico.

Cada conquista devolve o progresso, não só o sim ou não. Uma medalha trancada
que diz "3 de 10" convida; uma que só diz "trancada" é enfeite.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.history.store import Assistido


# A madrugada começa aqui. Antes disso ainda é "hoje à noite" para muita gente.
HORA_DA_MADRUGADA = 1
HORA_QUE_AMANHECE = 5


@dataclass(frozen=True)
class Conquista:
    codigo: str
    nome: str
    descricao: str
    atual: int
    alvo: int

    @property
    def conquistada(self) -> bool:
        return self.atual >= self.alvo

    def como_dicionario(self) -> dict:
        return {
            "codigo": self.codigo,
            "nome": self.nome,
            "descricao": self.descricao,
            # Nunca passa do alvo: "12 de 10" faria a barra estourar e a conta
            # parecer errada.
            "atual": min(self.atual, self.alvo),
            "alvo": self.alvo,
            "conquistada": self.conquistada,
        }


def _horas(segundos: float) -> float:
    return segundos / 3600


def _dias_distintos(historico: list[Assistido]) -> int:
    """Em quantos dias diferentes esta pessoa assistiu alguma coisa.

    Dia do relógio dela, não em UTC — pela mesma razão da madrugada logo abaixo.
    Medido no histórico real: três títulos vistos na mesma noite de 13/08, dois
    deles depois das 21h. Em UTC isso vira 13 e 14, e a conquista "Constante"
    anunciava dois dias de uma noite só.
    """
    dias = set()
    for item in historico:
        if item.visto_em <= 0:
            continue
        dias.add(datetime.fromtimestamp(item.visto_em).date())
    return len(dias)


def _assistiu_de_madrugada(historico: list[Assistido]) -> bool:
    for item in historico:
        if item.visto_em <= 0:
            continue
        # Hora local, não UTC: a madrugada de quem assiste é a do relógio dele.
        hora = datetime.fromtimestamp(item.visto_em).hour
        if HORA_DA_MADRUGADA <= hora < HORA_QUE_AMANHECE:
            return True
    return False


def calcular(historico: list[Assistido]) -> list[Conquista]:
    """As conquistas na ordem em que fazem sentido perseguir."""
    titulos = len(historico)
    terminados = sum(1 for item in historico if item.terminado)
    servicos = len({item.platform for item in historico if item.platform})
    generos = len({genero for item in historico for genero in item.generos})
    total_de_horas = _horas(sum(item.segundos for item in historico))
    maior_maratona = _horas(max((item.segundos for item in historico), default=0))
    dias = _dias_distintos(historico)

    por_servico: dict[str, float] = {}
    for item in historico:
        if item.platform:
            por_servico[item.platform] = por_servico.get(item.platform, 0) + item.segundos
    horas_no_favorito = _horas(max(por_servico.values(), default=0))

    return [
        Conquista(
            "PRIMEIRO_PLAY", "Primeiro play",
            "Assista alguma coisa por mais de 90 segundos.",
            titulos, 1,
        ),
        Conquista(
            "ATE_O_FIM", "Até o fim",
            "Termine um título — os créditos contam.",
            terminados, 1,
        ),
        Conquista(
            "MARATONA", "Maratona",
            "Três horas no mesmo título.",
            int(maior_maratona), 3,
        ),
        Conquista(
            "MADRUGADA", "Madrugada",
            "Assista alguma coisa entre 1h e 5h da manhã.",
            1 if _assistiu_de_madrugada(historico) else 0, 1,
        ),
        Conquista(
            "TURISTA", "Turista",
            "Assista em dois serviços diferentes.",
            servicos, 2,
        ),
        Conquista(
            "EXPLORADOR", "Explorador",
            "Assista em quatro serviços diferentes.",
            servicos, 4,
        ),
        Conquista(
            "ECLETICO", "Eclético",
            "Cinco gêneros diferentes no histórico.",
            generos, 5,
        ),
        Conquista(
            "COLECIONADOR", "Colecionador",
            "Dez títulos diferentes.",
            titulos, 10,
        ),
        Conquista(
            "DEVORADOR", "Devorador",
            "Termine cinco títulos.",
            terminados, 5,
        ),
        Conquista(
            "FIEL", "Fiel à casa",
            "Dez horas no mesmo serviço.",
            int(horas_no_favorito), 10,
        ),
        Conquista(
            "CONSTANTE", "Constante",
            "Assista em cinco dias diferentes.",
            dias, 5,
        ),
        Conquista(
            "CINQUENTA", "Cinquenta horas",
            "Cinquenta horas assistidas no total.",
            int(total_de_horas), 50,
        ),
    ]


def nivel(conquistas: list[Conquista]) -> dict:
    """O quanto o controle evoluiu, em uma linha.

    O nível é o número de conquistas: simples de explicar e impossível de
    manipular sem de fato assistir a alguma coisa.
    """
    conquistadas = [c for c in conquistas if c.conquistada]
    faltando = [c for c in conquistas if not c.conquistada]
    # A próxima é a mais perto de fechar, não a próxima da lista: é a que a
    # pessoa consegue alcançar hoje.
    proxima = max(faltando, key=lambda c: c.atual / c.alvo, default=None)
    return {
        "nivel": len(conquistadas),
        "total": len(conquistas),
        "proxima": proxima.como_dicionario() if proxima else None,
    }
