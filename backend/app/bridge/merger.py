"""Qual fonte responde por qual CAMPO — e por que nunca por uma sessão inteira.

Hoje o sistema tem duas decisões que não conversam (MEDIA_PIPELINE §8), e a
composição do resultado acontece dentro de uma função só, misturada com a
leitura. Quando o título sai errado, não há como responder "de onde veio este
título?".

Este módulo é a resposta. Ele não lê nada e não fala com o Windows: recebe o
que cada fonte declarou e devolve uma `SessaoCanonica` em que cada campo sabe
de onde veio.

## A regra: autoridade por campo, em ordem fixa

    currentTime      html-media-element  →  smtc
    workTitle        provider-adapter    →  window-title  →  smtc

O `<video>` da página SABE que segundo está tocando; a SMTC do Windows às vezes
sabe e às vezes devolve a linha do tempo da mídia anterior. Já o nome da obra o
`<video>` não sabe — quem sabe é o adapter do serviço, e depois a janela.

A mesma fonte é autoridade para um campo e não é para outro. É isso que impede
o modo de falha que o Master Loop proíbe: uma fonte ganhar a sessão inteira.
Uma SMTC que responde bem sobre tempo NÃO ganha o direito de nomear a obra.

## O que este módulo recusa a fazer

    último evento vence          timing não é autoridade
    última fonte registrada      ordem de chegada não é autoridade
    maior `confidence`           número mágico; ver `contratos.py`
    fonte inteira vence          proibição nº 5 do Master Loop
    empate resolvido por sorte   não há empate: a ordem é total

O resultado é determinístico. As mesmas entradas dão a mesma saída, hoje e
depois de reiniciar, e o motivo de cada campo é `procedencia()`.

## As cinco perguntas, nesta ordem

    1. quem é autoridade para este campo, e em que ordem?
    2. esta fonte respondeu?
    3. esta fonte tem CAPACIDADE para este campo neste serviço?
    4. o campo está FRESCO?
    5. a primeira que passa nas quatro vence.

A terceira e a quarta são diferentes, e confundi-las é o erro que a Fase 8
formaliza. A janela do Max SEMPRE tem título e ele SEMPRE é o do episódio: isso
é capacidade, não frescor — esperar mais não melhora. Já um `currentTime` de
trinta segundos atrás foi correto quando foi lido e não é mais: isso é frescor,
não capacidade.

Capacidade mora no `trustworthy` de cada `MediaField` — que é quem lê a fonte
que preenche, consultando `PLATAFORMAS_COM_OBRA_NA_JANELA`. Frescor mora na
`Leitura`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from app.bridge.contratos import Fonte, MediaField, SessaoCanonica


# ── A tabela ──────────────────────────────────────────────────────────────
#
# Ordem de autoridade por campo. Uma fonte que NÃO está na lista de um campo
# não pode preenchê-lo, nem que declare um valor perfeito. É assim que "fonte
# inteira vence" deixa de ser uma regra que alguém precisa lembrar e passa a ser
# uma coisa que a estrutura não permite escrever.
FIELD_AUTHORITY: dict[str, tuple[Fonte, ...]] = {
    # Tempo e estado técnico: o elemento da página é quem está lá.
    "currentTime": ("html-media-element", "smtc"),
    "duration": ("html-media-element", "smtc"),
    "playbackState": ("html-media-element", "smtc"),
    "playbackRate": ("html-media-element", "smtc"),
    "audible": ("html-media-element", "smtc"),
    "muted": ("html-media-element", "smtc"),

    # Identidade da obra: o adapter do serviço primeiro, a janela depois.
    # A janela NÃO aparece em nenhum campo de tempo — ela não mede nada.
    "workTitle": ("provider-adapter", "window-title", "smtc"),
    "episodeTitle": ("provider-adapter", "window-title", "smtc"),
    "seasonNumber": ("provider-adapter", "window-title", "smtc"),
    "episodeNumber": ("provider-adapter", "window-title", "smtc"),
    "mediaType": ("provider-adapter", "window-title", "smtc"),
    "provider": ("provider-adapter", "window-title", "smtc"),
}

# Campos que envelhecem. Um `currentTime` de um minuto atrás está errado agora;
# o nome da obra de um minuto atrás continua sendo o nome da obra.
#
# É a assimetria que a Fase 8 vai detalhar, e ela precisa existir já aqui: sem
# ela, "fonte prioritária stale" não teria como ser diferente de "fonte
# prioritária ausente".
CAMPOS_DINAMICOS: frozenset[str] = frozenset({
    "currentTime", "duration", "playbackState", "playbackRate", "audible", "muted",
})


@dataclass(frozen=True)
class Leitura:
    """O que UMA fonte tem a dizer neste instante.

    Só os campos que ela declara. Não declarar é diferente de declarar nada: a
    SMTC pendurada não declara, e a SMTC que respondeu sem metadata declara
    `MediaField.ausente()`. Para o Merger os dois casos dão no mesmo, mas o
    diagnóstico não é o mesmo, e a `Leitura` preserva a diferença.
    """

    fonte: Fonte
    campos: Mapping[str, MediaField] = field(default_factory=dict)
    #: Os campos dinâmicos desta fonte ainda valem?
    #:
    #: Entrada, não conclusão: quem sabe medir isso é a Fase 8. Aqui é o
    #: interruptor que permite a uma fonte estar VIVA para metadata e velha
    #: para tempo — que é exatamente o estado da SMTC quando ela devolve a
    #: linha do tempo da mídia anterior com o título certo.
    dinamicos_frescos: bool = True

    def oferta(self, campo: str) -> MediaField | None:
        """O que esta fonte oferece para o campo, se puder oferecer."""
        valor = self.campos.get(campo)
        if valor is None or not valor.utilizavel:
            return None
        if campo in CAMPOS_DINAMICOS and not self.dinamicos_frescos:
            return None
        return valor


def fundir(leituras: list[Leitura]) -> SessaoCanonica:
    """A sessão canônica: campo a campo, cada um com a sua procedência.

    Nenhuma fonte é lida "inteira". O laço é por CAMPO, e para cada campo a
    ordem é a da tabela — não a ordem em que as leituras chegaram, não a
    ordem em que foram registradas, não a hora do evento.
    """
    por_fonte: dict[Fonte, Leitura] = {}
    for leitura in leituras:
        # Duas leituras da mesma fonte: a última substitui. Isso é a fonte se
        # atualizando, não duas fontes disputando — e continua sem afetar
        # nenhum outro campo.
        por_fonte[leitura.fonte] = leitura

    resolvidos: dict[str, MediaField] = {}
    for campo in SessaoCanonica.__annotations__:
        resolvidos[campo] = _decidir(campo, por_fonte)
    return SessaoCanonica(**resolvidos)


def _decidir(campo: str, por_fonte: dict[Fonte, Leitura]) -> MediaField:
    for fonte in FIELD_AUTHORITY.get(campo, ()):
        leitura = por_fonte.get(fonte)
        if leitura is None:
            continue
        oferta = leitura.oferta(campo)
        if oferta is not None:
            return oferta
    return MediaField.ausente()
