"""A obra e a reprodução são duas coisas, e o sistema tratava as duas como uma.

Este é o defeito que estava por trás de três sintomas que pareciam separados.

    Loki sumiu de "continuar assistindo" para sempre.
    "Batman: Caped Crusader" dizia "faltam 20 min" numa série já terminada.
    "Família Soprano" parou de contar tempo quando a SMTC pendurou.

Os três saem da mesma confusão: `posicao` e `duracao` descrevem o EPISÓDIO que
está tocando, e ficavam guardados na linha da OBRA, onde `terminado` os lia como
se descrevessem a série inteira.

Medido no histórico real deste computador, em 17/08/2026:

    DISNEY_PLUS::loki   segundos 30444   posicao 2226,5 / duracao 2241,2

Trinta mil segundos são oito horas e meia — a série. Dois mil e duzentos são
trinta e sete minutos — um episódio. A razão 2226/2241 = 0,9935 passou do corte
de 0,94, e a obra inteira foi marcada como terminada porque UM episódio acabou.

E a armadilha fechava depois: sem posição nova, `registrar` herdava a posição
antiga, então nenhuma quantidade de episódios seguintes desfazia a marca. Está
provado em `test_history_identidade.py`: uma hora do episódio seguinte, e a
série continuava fora da tela.

## As duas identidades

    IdentidadeDaObra         o que entra no histórico, no catálogo e na tela.
                             Estável entre episódios. É a série.

    IdentidadeDaReproducao   o que está tocando AGORA. Muda a cada episódio.
                             É dela que posição e duração falam.

Trocar de episódio muda a segunda e NÃO a primeira. Era essa frase que faltava.

## Por que a duração faz parte da reprodução

Nem sempre há nome de episódio: ele só aparece quando as DUAS fontes respondem
(a SMTC nomeia a série, a janela nomeia o episódio — ver `episodio_da_janela`).
Quando só uma responde, o nome do episódio não existe, e a duração é o que
sobra para dizer que a reprodução mudou. Dois episódios com duração idêntica ao
segundo se confundem; é pouco, e é muito melhor do que herdar a posição de uma
reprodução que acabou.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.platform import Platform


@dataclass(frozen=True)
class IdentidadeDaObra:
    """A obra. O que o histórico conta e o catálogo procura.

    Serviço junto do nome de propósito: "O Justiceiro" é um filme de 2004 no Max
    e uma série da Marvel no Disney+, e o histórico já tratava os dois como
    obras diferentes — ver `_mesma_obra` em `history/store.py`.
    """

    titulo: str
    platform: Platform | None

    def __post_init__(self) -> None:
        if not self.titulo.strip():
            raise ValueError("uma obra sem nome não é uma identidade")


@dataclass(frozen=True)
class IdentidadeDaReproducao:
    """O que está tocando agora, dentro da obra.

    Um filme tem uma só, e ela dura a obra inteira. Uma série tem uma por
    episódio, e é isso que faz `posicao` e `duracao` mudarem de significado no
    meio da sessão.
    """

    obra: IdentidadeDaObra
    episodio: str | None = None
    duracao: float | None = None

    @property
    def chave(self) -> str | None:
        return chave_da_reproducao(self.episodio, self.duracao)


def chave_da_reproducao(episodio: str | None, duracao: float | None) -> str | None:
    """Duas leituras da MESMA reprodução dão a mesma chave.

    É o que autoriza herdar a posição de uma leitura para a seguinte — e o que
    proíbe herdá-la quando o episódio virou.

    `None` quando não há nem nome nem duração: aí não se sabe de que reprodução
    se fala, e fingir uma chave faria duas reproduções desconhecidas passarem
    por iguais.

    A duração entra arredondada ao segundo: a SMTC devolve casas decimais que
    oscilam entre leituras da mesma reprodução, e sem o arredondamento cada
    leitura viraria uma reprodução nova.
    """
    nome = (episodio or "").strip().lower()
    if not nome and not duracao:
        return None
    return f"{nome}|{round(duracao) if duracao else ''}"


# Quantas vezes a duração de UMA reprodução o tempo acumulado precisa passar
# para a linha ser, com certeza, de mais de uma reprodução.
#
# 1,5 e não 1,0: o tempo acumulado é medido por amostragem do laço e passa um
# pouco do real. Um filme visto uma vez fica abaixo; um visto duas vezes fica
# acima e é tratado como multi-reprodução — o lado seguro do erro, porque a
# consequência é continuar na lista em vez de sumir dela.
FATOR_DE_MULTIPLAS_REPRODUCOES = 1.5


def de_multiplas_reproducoes(
    segundos: float,
    duracao: float | None,
    viu_episodio: bool,
) -> bool:
    """Esta linha junta mais de uma reprodução?

    Duas evidências, e basta uma:

    1. Já se viu um nome de episódio. Prova direta.
    2. O tempo acumulado passa da duração de uma reprodução. Prova indireta e
       que não depende de fonte nenhuma: 7850 segundos assistidos contra uma
       duração de 1680 não cabem num episódio só. Foi o que desmascarou
       "Batman: Caped Crusader" — uma série que o histórico media com a régua
       de um episódio e anunciava "faltam 20 min".

    A segunda existe porque a primeira quase nunca está disponível: o nome do
    episódio só aparece quando a SMTC E a janela respondem juntas, e a SMTC
    passa boa parte do tempo pendurada.
    """
    if viu_episodio:
        return True
    if duracao is None or duracao <= 0:
        return False
    return segundos > duracao * FATOR_DE_MULTIPLAS_REPRODUCOES
