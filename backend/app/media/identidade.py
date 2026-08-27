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
import re

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

    @property
    def chave(self) -> str:
        """A chave da OBRA. Não inclui temporada nem episódio, e é esse o ponto.

        Fase 11: "Rick and Morty" S01E01 → S01E02 → S01E03 muda a
        `IdentidadeDaReproducao` três vezes e NÃO muda esta. Uma obra no
        histórico, e não três — que é a fragmentação por episódio que o gate da
        Fase 12 proíbe.
        """
        import unicodedata

        limpo = unicodedata.normalize("NFKD", self.titulo.strip().lower())
        sem_acento = "".join(c for c in limpo if not unicodedata.combining(c))
        return f"{self.platform or '-'}::{' '.join(sem_acento.split())}"


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

    #: O que a página disse desta reprodução, quando há adapter.
    page_id: str | None = None
    temporada: int | None = None
    episodio_numero: int | None = None

    @property
    def chave(self) -> str | None:
        return identidade_da_reproducao(
            self.page_id, self.temporada, self.episodio_numero,
            self.episodio, self.duracao,
        )


def identidade_da_reproducao(
    page_id: str | None = None,
    temporada: int | None = None,
    episodio_numero: int | None = None,
    episodio: str | None = None,
    duracao: float | None = None,
) -> str | None:
    """A chave da reprodução, do sinal mais forte para o mais fraco.

    Fase 11. A versão anterior tinha uma fonte só — nome do episódio mais
    duração — porque era tudo o que existia. Agora a página fala, e ela fala
    melhor do que qualquer inferência:

        page_id                 "/watch/81234567". A própria Netflix dizendo
                                qual reprodução é. Não depende de nome, não
                                depende de duração, e muda no episódio seguinte.

        temporada + episódio    "s1e4". Estável entre releituras e legível em
                                log, o que a duração não é.

        nome + duração          o que já existia. Continua valendo para os
                                serviços sem adapter, que são a maioria.

    A ordem importa mais do que parece: misturar os sinais numa chave só faria
    a mesma reprodução gerar chaves diferentes conforme o que a leitura
    conseguiu ler naquele segundo — e duas chaves para a mesma reprodução é
    exatamente o que faz o histórico achar que trocou de episódio e recalibrar
    a posição sem motivo.
    """
    if page_id is not None and str(page_id).strip():
        return f"id:{str(page_id).strip()}"
    if temporada is not None and episodio_numero is not None:
        return f"s{temporada}e{episodio_numero}"
    return chave_da_reproducao(episodio, duracao)


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


# ── Temporada e episódio, quando o serviço os publica ─────────────────────

# As grafias que os serviços usam de verdade. A lista é curta de propósito:
# inventar padrões "que poderiam existir" só cria formas novas de casar errado.
_PADROES_DE_EPISODIO = (
    # "S1:E4", "S01E04", "S1 E4"
    re.compile(r"\bS(?P<t>\d{1,2})\s*[:xE\s-]\s*E?(?P<e>\d{1,3})\b", re.IGNORECASE),
    # "T1:E4", "T01 EP04" — a grafia em português
    re.compile(r"\bT(?P<t>\d{1,2})\s*[:x\s-]\s*EP?\s*(?P<e>\d{1,3})\b", re.IGNORECASE),
    # "Temporada 1, Episódio 4"
    re.compile(
        r"\btemporada\s*(?P<t>\d{1,2}).{0,4}epis[oó]dio\s*(?P<e>\d{1,3})\b",
        re.IGNORECASE,
    ),
    # "1x04", a forma antiga que ainda aparece
    re.compile(r"\b(?P<t>\d{1,2})x(?P<e>\d{2,3})\b"),
)


#: O que separa obra, marcador e nome do episódio num título de aba.
_SEPARADORES_DO_TITULO = " -–—|•·:"


def separar_obra_e_episodio(titulo: str | None) -> tuple[str, str | None] | None:
    """"Invincible - S1 E4 - Neil Armstrong" → ("Invincible", "T1 E4 · Neil Armstrong").

    ## O bug que isto conserta

    Medido em 26/08/2026, contra os formatos reais de Prime Video e Disney+:

        "Prime Video: Invincible - S1 E4 - Neil Armstrong"
            → obra = "Invincible - S1 E4 - Neil Armstrong"

        "Demolidor: Renascido - T1 E5 - Com Sangue | Disney+"
            → obra = "Demolidor: Renascido - T1 E5 - Com Sangue"

    O marcador ficava DENTRO do nome da obra. Consequência em três lugares ao
    mesmo tempo: uma linha de histórico por episódio, nenhum pôster (o catálogo
    não conhece "Invincible - S1 E4 - Neil Armstrong") e nenhum T/E — que
    estavam ali, escritos, e eram jogados fora.

    É o mesmo defeito do "sherlock season 2", numa terceira forma. As duas
    anteriores eram a temporada no fim e a temporada no meio; esta é a
    temporada COM o nome do episódio depois dela.

    ## Por que só corta quando há algo DEPOIS do marcador

    Porque é isso que distingue as duas leituras possíveis:

        "Obra - S1 E4 - Episódio"   o que vem antes é a obra. Certeza.
        "Episódio • T5 E14"         o que vem antes pode ser o episódio, e é
                                    exatamente o que o Max faz.

    Sem nada depois, não há como saber de qual dos dois se trata, e chutar
    poria o nome de um episódio na linha da obra — o defeito que
    `PLATAFORMAS_COM_OBRA_NA_JANELA` existe para impedir. Aí só os números são
    aproveitados, e o texto fica como está.

    `None` quando não há marcador nenhum, que é o caso da maioria dos títulos.
    """
    if not titulo or not titulo.strip():
        return None

    for padrao in _PADROES_DE_EPISODIO:
        achado = padrao.search(titulo)
        if achado is None:
            continue
        temporada, episodio = int(achado.group("t")), int(achado.group("e"))
        if not (1 <= temporada <= 50 and 1 <= episodio <= 999):
            continue

        antes = titulo[: achado.start()].strip(_SEPARADORES_DO_TITULO).strip()
        depois = titulo[achado.end():].strip(_SEPARADORES_DO_TITULO).strip()
        if not antes or not depois:
            return None

        rotulo = f"T{temporada} E{episodio}"
        return antes, f"{rotulo} · {depois}"
    return None


def temporada_e_episodio(texto: str | None) -> tuple[int, int] | None:
    """Os números da temporada e do episódio, quando o texto os traz.

    `None` quando não traz — e esse é o caso COMUM, não a exceção. Medido em
    19/08/2026 com Ben 10 no Max: a janela publica
    "⁨Enganados Enganados⁩ • HBO Max", só o nome do episódio. O Max não põe
    número nenhum ali, e a API de mídia do Windows estava pendurada.

    Quem sabe os números é a PÁGINA, e chegar até ela é o trabalho do Browser
    Media Bridge. Enquanto ele não estiver ligado, esta função devolve `None`
    na maior parte das vezes — e devolver `None` é o certo. Um "T1 E1"
    inventado seria pior do que número nenhum: a pessoa acreditaria nele.
    """
    if not texto:
        return None
    for padrao in _PADROES_DE_EPISODIO:
        achado = padrao.search(texto)
        if achado is None:
            continue
        temporada, episodio = int(achado.group("t")), int(achado.group("e"))
        # Zero não existe em nenhuma das duas contagens; números altos demais
        # são ano ou parte do nome.
        if 1 <= temporada <= 50 and 1 <= episodio <= 999:
            return temporada, episodio
    return None


#: "E1" ou "T2" sozinhos, que é como a Netflix escreve na maior parte do tempo.
_SO_EPISODIO = re.compile(r"^E(?:P)?\s*(\d{1,3})\b", re.IGNORECASE)
_SO_TEMPORADA = re.compile(r"^T(?:emporada)?\s*(\d{1,2})\b", re.IGNORECASE)


def como_temporada_e_episodio(texto: str | None) -> str | None:
    """"T1 E4" — ou "E4", quando a temporada não foi publicada.

    A tela precisa da forma curta, e a forma curta tem de ser HONESTA sobre o
    que se sabe. Medido em 26/08/2026 com Breaking Bad na Netflix: o player
    publica "E1" e nada mais quando já se sabe em que temporada se está.

    Completar com "T1" seria um palpite, e ele erra justamente para quem mais
    precisa da informação — quem está na quinta temporada e veria "T1 E1".
    """
    numeros = temporada_e_episodio(texto)
    if numeros is not None:
        temporada, episodio = numeros
        return f"T{temporada} E{episodio}"

    if not texto:
        return None
    # Sem os dois juntos, vale o que houver sozinho.
    episodio = _SO_EPISODIO.match(texto.strip())
    if episodio is not None and 1 <= int(episodio.group(1)) <= 999:
        return f"E{int(episodio.group(1))}"
    temporada = _SO_TEMPORADA.match(texto.strip())
    if temporada is not None and 1 <= int(temporada.group(1)) <= 50:
        return f"T{int(temporada.group(1))}"
    return None
