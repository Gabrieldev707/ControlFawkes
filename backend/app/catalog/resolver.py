"""Qual obra do catálogo é esta mídia — e por quê.

O resolver antigo fazia geração e escolha no mesmo `max()`, sobre uma página só
de `/search/multi`. Medido em 15/08/2026 com "O Rei" tocando:

    O filme certo — `O Rei` / `The King` / 2019 — NÃO estava entre os 20
    resultados, nem na página 3 de 57. Ele não perdeu a disputa: ele nunca
    entrou nela.

E a conclusão que isso força é contra-intuitiva: **a popularidade não era a
culpada**. O de 2019 tem popularidade 6,63 contra 2,01 do homônimo de 2014 —
se estivesse na lista, o desempate por fama já o teria escolhido certo. O
defeito era de RECALL, na geração.

Daí a separação deste módulo:

    geração    quais obras PODEM plausivelmente ser esta mídia?  (recall alto)
    ranking    qual delas é mais compatível?                     (determinístico)
    ambiguidade  e quando não dá para saber, dizer que não dá.

## Título não é identidade

Um nome como "O Rei" não identifica nada: existem dezenas. O que identifica é o
conjunto — nome, ano, tipo e, quando houver, o id da obra dentro do próprio
serviço. Por isso `Observado` carrega tudo o que se sabe, e não só o texto.

## A popularidade fica no fim, e com trava

Ela só decide entre candidatos que empataram no MESMO nível estrutural, e só
quando a diferença é decisiva (ver `FATOR_DE_DESEMPATE`). Empate apertado não
vira escolha: vira `Ambiguo`. É melhor "O Rei" sem enriquecimento do que
"O Rei" com o pôster de outro filme e o histórico contaminado.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import IntEnum
import unicodedata


TipoDeObra = str  # "MOVIE" | "TV"

# Quanto mais popular o primeiro precisa ser para a fama valer como desempate.
#
# Dois de propósito, e não 1,1: a popularidade só entra quando a diferença é
# grande o bastante para ser sinal em vez de ruído. Medido — "O Rei" (2019, 6,63)
# contra "O Rei" (2014, 2,01) dá 3,3x e decide; "The Gentlemen" filme (16,81)
# contra série (30,31) dá 1,8x e NÃO decide, porque são obras diferentes com o
# mesmo nome e ninguém sabe qual está tocando.
FATOR_DE_DESEMPATE = 2.0

# Acima disto dois nomes são "quase o mesmo": acento perdido, plural trocado,
# uma letra de diferença. Foi o que salvou "the gentleman" contra
# "the gentlemen".
SIMILARIDADE_MINIMA = 0.9

# Palavras que não identificam obra nenhuma.
_LIGACOES = {"e", "o", "a", "os", "as", "de", "da", "do", "the", "and", "of"}

# Palavras que nomeiam o SERVIÇO, não a obra. Aconteceu na tela: o histórico
# guardou "Prime Video: Batman: Caped Crusader" e a capa que apareceu foi a de
# "Prime Video Boxing 11" — duas palavras longas em comum, e nada a ver.
_NOMES_DE_SERVICO = {
    "prime", "video", "netflix", "disney", "plus", "hbo", "youtube", "spotify",
    "amazon", "star", "globoplay",
}

# Abaixo disto a palavra aparece em metade do catálogo e não prova nada.
_LETRAS_DE_PALAVRA_FORTE = 4


class Nivel(IntEnum):
    """Força da correspondência. Menor é melhor.

    A ordem é a resposta a "por que este candidato venceu?" — e ela é fixa, não
    emergente. Um candidato de nível 3 NUNCA perde para um de nível 5, por mais
    famoso que o segundo seja.
    """

    #: A obra já foi associada a este id dentro do provider. Identidade, não palpite.
    PROVIDER_ID = 0
    TITULO_ANO_TIPO = 1
    ALTERNATIVO_ANO_TIPO = 2
    TITULO_TIPO = 3
    TITULO = 4
    #: Mesmo nome a menos de artigo e pontuação. Medido: o serviço mostra
    #: "Batman: Cruzado e Encapuzado" e o catálogo guarda "Batman: Cruzado
    #: Encapuzado" — um "e" de diferença. Isso é MUITO mais forte do que
    #: "parecido", e sem um degrau próprio caía junto com ele.
    ALTERNATIVO = 5
    SIMILAR_ANO = 6
    SIMILAR = 7
    #: Um nome é o COMEÇO do outro: subtítulo, temporada, parte. "Duna" e
    #: "Duna: Parte Dois"; "Batman: Cruzado Encapuzado" e "Batman: O Cruzado
    #: Encapuzado Ressurge".
    SUBTITULO = 8
    #: Dividem uma palavra que identifica alguma coisa. É o degrau mais fraco, e
    #: existe por causa da tradução: "Caped Crusader" virou "Cruzado
    #: Encapuzado", e só "Batman" sobreviveu.
    PALAVRA_FORTE = 9
    #: Não responde à consulta. Sai da disputa.
    NENHUM = 10


def normalizar(texto: str) -> str:
    """Sem acento, sem pontuação, sem caixa, sem espaço sobrando."""
    decomposto = unicodedata.normalize("NFKD", texto.strip().lower())
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    limpo = "".join(c if c.isalnum() or c.isspace() else " " for c in sem_acento)
    return " ".join(limpo.split())


def sem_ligacoes(texto: str) -> str:
    """"O Rei" e "The King" viram "rei" e "king".

    Serve para comparar, nunca para buscar: encurtar a consulta enviada ao
    catálogo é o que fazia "Prime Video: Batman" virar "Prime Video" e devolver
    um evento de boxe.
    """
    return " ".join(p for p in normalizar(texto).split() if p not in _LIGACOES)


@dataclass(frozen=True)
class Observado:
    """Tudo o que se sabe da mídia que está tocando.

    Só `titulo` é obrigatório porque, hoje, muitas vezes é só o que existe. Cada
    campo a mais estreita a busca — e o `ano` é o que mais estreita: medido, com
    ele o filme certo sobe da página 2 para a 3ª posição.
    """

    titulo: str
    ano: int | None = None
    tipo: TipoDeObra | None = None
    provider: str | None = None
    #: Id da obra DENTRO do provider (`/watch/81043710` da Netflix, ASIN do
    #: Prime). Não é id do TMDB — é identidade local forte. Ver `identidades.py`.
    providerContentId: str | None = None


@dataclass(frozen=True)
class Candidato:
    tmdb_id: int
    tipo: TipoDeObra
    titulo: str
    #: Todos os nomes: exibição, original, e alternativos quando houver.
    nomes: tuple[str, ...]
    ano: int | None
    popularidade: float
    poster_path: str | None = None
    #: Gêneros por id, como a busca os devolve. Evita uma segunda ida ao
    #: catálogo só para traduzir números em nomes.
    genre_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class Avaliacao:
    candidato: Candidato
    nivel: Nivel
    motivo: str


@dataclass(frozen=True)
class Escolhido:
    candidato: Candidato
    nivel: Nivel
    #: Frase legível: é a resposta a "por que este venceu?".
    motivo: str


@dataclass(frozen=True)
class Ambiguo:
    """Havia mais de um candidato igualmente plausível.

    NÃO é falha. É a resposta correta quando a informação observada não
    distingue — e vale mais do que anexar o pôster de outra obra.
    """

    candidatos: tuple[Candidato, ...]
    motivo: str


@dataclass(frozen=True)
class SemCandidato:
    motivo: str


Resultado = Escolhido | Ambiguo | SemCandidato


def _casa_exato(candidato: Candidato, observado: Observado) -> bool:
    alvo = normalizar(observado.titulo)
    return any(normalizar(nome) == alvo for nome in candidato.nomes)


def _casa_exato_sem_ligacoes(candidato: Candidato, observado: Observado) -> bool:
    alvo = sem_ligacoes(observado.titulo)
    if not alvo:
        return False
    return any(sem_ligacoes(nome) == alvo for nome in candidato.nomes)


def _casa_parecido(candidato: Candidato, observado: Observado) -> bool:
    alvo = normalizar(observado.titulo)
    return any(
        SequenceMatcher(None, normalizar(nome), alvo).ratio() >= SIMILARIDADE_MINIMA
        for nome in candidato.nomes
    )


def _palavras_fortes(texto: str) -> set[str]:
    """As palavras que identificam a obra, e só elas."""
    return {
        p for p in normalizar(texto).split()
        if len(p) >= _LETRAS_DE_PALAVRA_FORTE and p not in _NOMES_DE_SERVICO
    }


def _e_comeco_de(curto: list[str], longo: list[str]) -> bool:
    """`curto` é o começo de `longo`, contado em palavras inteiras.

    Em palavras e não em letras: por letra, "Duna" casaria com "Dunas do Mar",
    que é outra obra.
    """
    if not curto or len(curto) >= len(longo):
        return False
    if longo[: len(curto)] != curto:
        return False
    # E o começo em comum tem de dizer alguma coisa. "Prime Video" é o começo
    # de "Prime Video Boxing 11" e de "Prime Video: Batman" — e as duas obras
    # não têm nada a ver uma com a outra.
    return any(
        len(p) >= _LETRAS_DE_PALAVRA_FORTE and p not in _NOMES_DE_SERVICO
        for p in curto
    )


def _um_e_comeco_do_outro(candidato: Candidato, observado: Observado) -> bool:
    alvo = sem_ligacoes(observado.titulo).split()
    for bruto in candidato.nomes:
        nome = sem_ligacoes(bruto).split()
        if _e_comeco_de(alvo, nome) or _e_comeco_de(nome, alvo):
            return True
    return False


def _divide_palavra_forte(candidato: Candidato, observado: Observado) -> bool:
    do_observado = _palavras_fortes(observado.titulo)
    if not do_observado:
        # Nome curto demais para ser comparado assim ("Duna"). Barrar aqui seria
        # inventar uma reprovação que a regra não sabe dar.
        return False
    return any(_palavras_fortes(nome) & do_observado for nome in candidato.nomes)


def _mesmo_ano(candidato: Candidato, observado: Observado) -> bool:
    if observado.ano is None or candidato.ano is None:
        return False
    # Um ano de folga: data de estreia varia por país, e o serviço costuma
    # mostrar a do lançamento local.
    return abs(candidato.ano - observado.ano) <= 1


def _mesmo_tipo(candidato: Candidato, observado: Observado) -> bool:
    return observado.tipo is not None and candidato.tipo == observado.tipo


def classificar(
    candidato: Candidato,
    observado: Observado,
    associado: int | None = None,
) -> Avaliacao:
    """Em que nível este candidato responde ao observado.

    `associado` é o id do TMDB que já foi ligado a `(provider, contentId)` numa
    resolução anterior. Ele ganha de tudo — é identidade guardada, não palpite
    refeito.
    """
    if associado is not None and candidato.tmdb_id == associado:
        return Avaliacao(
            candidato, Nivel.PROVIDER_ID,
            f"id já associado a {observado.provider}:{observado.providerContentId}",
        )

    exato = _casa_exato(candidato, observado)
    ano = _mesmo_ano(candidato, observado)
    tipo = _mesmo_tipo(candidato, observado)

    if exato and ano and tipo:
        return Avaliacao(candidato, Nivel.TITULO_ANO_TIPO, "título, ano e tipo exatos")
    if _casa_exato_sem_ligacoes(candidato, observado) and ano and tipo:
        return Avaliacao(
            candidato, Nivel.ALTERNATIVO_ANO_TIPO, "nome alternativo com ano e tipo",
        )
    if exato and tipo:
        return Avaliacao(candidato, Nivel.TITULO_TIPO, "título exato e tipo")
    if exato:
        return Avaliacao(candidato, Nivel.TITULO, "título exato")
    if _casa_exato_sem_ligacoes(candidato, observado):
        return Avaliacao(candidato, Nivel.ALTERNATIVO, "mesmo nome a menos de artigo")
    if _casa_parecido(candidato, observado) and ano:
        return Avaliacao(candidato, Nivel.SIMILAR_ANO, "título parecido com o mesmo ano")
    if _casa_parecido(candidato, observado):
        return Avaliacao(candidato, Nivel.SIMILAR, "título parecido")
    if _um_e_comeco_do_outro(candidato, observado):
        return Avaliacao(candidato, Nivel.SUBTITULO, "um nome é o começo do outro")
    if _divide_palavra_forte(candidato, observado):
        return Avaliacao(candidato, Nivel.PALAVRA_FORTE, "dividem uma palavra que identifica")
    return Avaliacao(candidato, Nivel.NENHUM, "não responde ao título observado")


def tem_candidato_forte(avaliacoes: list[Avaliacao]) -> bool:
    """Já dá para parar de procurar?

    É o freio da expansão progressiva: mais recall não é varrer o catálogo
    inteiro. Mas o freio precisa ser bem calibrado, e a primeira versão errou —
    ela parava em `Nivel.TITULO`, casamento só de nome.

    Medido contra a API: para "O Rei" a página 1 já traz um "O Rei" (2014)
    exato, o freio disparava, e o filme certo — que está na página 2 — nunca
    entrava no pool. O freio recriava o bug que ele deveria evitar.

    Um nome sozinho não é identidade, e num título genérico ele é quase nada.
    Só para de procurar o que veio confirmado por algo ALÉM do nome: tipo, ano,
    ou identidade guardada do provider.

    Esta trava governa as PÁGINAS. A do encurtamento é outra — ver
    `tem_casamento_exato`.
    """
    return any(a.nivel <= Nivel.TITULO_TIPO for a in avaliacoes)


def tem_casamento_exato(avaliacoes: list[Avaliacao]) -> bool:
    """Alguém já casa pelo nome inteiro?

    Trava do encurtamento de consulta, que responde outra pergunta: aquele
    recuo existe porque a busca do TMDB é LITERAL — "Batman: Cruzado e
    Encapuzado" devolve nada e "Batman: Cruzado Encapuzado" devolve tudo. Ele é
    para quando a grafia não achou NADA.

    Com um casamento exato na mão, encurtar só acrescenta ruído — e ruído aqui
    tem histórico: foi encurtando que "Prime Video: Batman" virou a consulta
    "Prime Video" e trouxe um evento de boxe.

    `ALTERNATIVO` conta como achado: "mesmo nome a menos de artigo" é
    justamente o que o encurtamento ia buscar.
    """
    return any(a.nivel <= Nivel.ALTERNATIVO for a in avaliacoes)


def resolver(
    candidatos: list[Candidato],
    observado: Observado,
    associado: int | None = None,
) -> Resultado:
    """A escolha, com o motivo — ou a recusa honesta de escolher."""
    avaliados = [
        a for a in (classificar(c, observado, associado) for c in candidatos)
        if a.nivel != Nivel.NENHUM
    ]
    if not avaliados:
        return SemCandidato("nenhum candidato responde ao título observado")

    melhor_nivel = min(a.nivel for a in avaliados)
    empatados = [a for a in avaliados if a.nivel == melhor_nivel]

    if len(empatados) == 1:
        unico = empatados[0]
        return Escolhido(unico.candidato, unico.nivel, unico.motivo)

    # Empate no mesmo nível estrutural. Só agora a popularidade fala — e só se
    # ela for decisiva.
    por_fama = sorted(empatados, key=lambda a: a.candidato.popularidade, reverse=True)
    primeiro, segundo = por_fama[0], por_fama[1]

    if segundo.candidato.popularidade <= 0:
        margem = float("inf") if primeiro.candidato.popularidade > 0 else 1.0
    else:
        margem = primeiro.candidato.popularidade / segundo.candidato.popularidade

    if margem >= FATOR_DE_DESEMPATE:
        return Escolhido(
            primeiro.candidato,
            primeiro.nivel,
            f"{primeiro.motivo}; desempate por popularidade ({margem:.1f}x)",
        )

    return Ambiguo(
        tuple(a.candidato for a in por_fama),
        (
            f"{len(empatados)} candidatos com {melhor_nivel.name.lower()} e "
            f"popularidade próxima ({margem:.1f}x) — falta ano ou tipo para decidir"
        ),
    )
