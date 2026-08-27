"""Fase 15 — qual aba a pessoa está assistindo.

```text
Media Merger          = resolve os CAMPOS de uma sessão
MediaSessionArbiter   = decide QUAL sessão é a ativa
```

O Merger responde "qual fonte sabe o `currentTime`?". Este arquivo responde uma
pergunta anterior e diferente: **de qual aba estamos falando?**

## De onde a ordem abaixo saiu

Não de intuição. O gate da Fase 14 proíbe, com todas as letras, congelar esta
política antes dos dados, e por isso `telemetria.py` passou dias só observando.
O que segue foi lido de `data/bridge/abas.jsonl` em 26/08/2026 — 1542
observações, 1526 delas com telemetria de aba, dos cinco serviços.

E a primeira coisa que os dados fizeram foi desmentir a leitura crua deles.

### O dataset estava contaminado, e por um bug nosso

Contando SESSÕES, havia 477 instantes com duas tocando. Contando ABAS, há 18.

    instantes com sessões repetidas na mesma aba   1078 de 1526
    maior número de sessões numa única aba         8

Eram sessões fantasma da mesma aba — o defeito corrigido em
`EstadoDaPonte._esquecer_a_mesma_aba`. Escrever o árbitro sobre o número cru
teria sido otimizar um conflito vinte e seis vezes mais raro do que ele
parecia. Ver `telemetria.uma_por_aba`.

### O que cada sinal respondeu, nos 18 instantes reais

    ACTIVE    aponta exatamente uma em 12; VÁRIAS em 6; nunca nenhuma
    AUDIBLE   aponta exatamente uma em  4; NENHUMA em 14

`active` várias vezes são janelas diferentes, cada uma com a sua aba
selecionada. `audible` quase nunca isola alguém.

### O achado que define a ordem

    aba ATIVA, tocando, com `audible === False`:  187 de 276  (68%)

Dois terços das vezes, a aba que a pessoa está olhando e que está tocando
declara não ser audível. É o mesmo defeito que a Fase 9 pagou caro para
aprender — lá, `audible` vetando fez o histórico parar de gravar por duas
horas — e agora ele tem número.

**Então `audible` promove e NUNCA rebaixa.** Um `False` aqui não é "não está
tocando"; é "não sei". Esta é a regra que mais custou neste projeto, e ela
aparece pela terceira vez: em `consumo.py`, em `audio_activity.py` e aqui.

### E os sinais que não dão para exigir

    windowFocused   presente em 29% das abas. Exigi-lo derrubaria a maioria.
    visible         diverge de `active` em 416 casos — não é sinônimo dele.
                    Uma aba ativa numa janela minimizada não está visível.

## A ordem, e por que ela é LEXICOGRÁFICA

Uma pontuação somada deixaria três sinais fracos derrubarem um forte, e
ninguém saberia dizer por quê depois. Comparação lexicográfica responde sempre
"venceu por causa DESTE critério" — e é isso que torna a troca entre abas
previsível, que é o que o gate desta fase pede.

## O que este arquivo NÃO decide

Não conta tempo assistido (`consumo.py`), não resolve campo (`merger.py`), não
lê nome de obra (os adapters). E é PURO: recebe a lista, devolve um elemento.
Sem estado, sem relógio próprio, sem efeito — não há corrida possível porque
não há nada a corromper.

## PICTURE-IN-PICTURE: a decisão que NÃO foi tomada

O plano lista PiP entre os sinais possíveis, e o raciocínio é conhecido — o
vídeo sai para a janelinha flutuante, a aba vai para segundo plano, e a pessoa
continua assistindo. É o caso que quebra "aba ativa é quem assiste".

**Só que ele tem ZERO observações em 1526.** Nunca aconteceu no uso real.

Então ele não entra na ordem. Não por esquecimento: por disciplina. Rankear um
sinal sem nenhuma medição é exatamente como nasceu o `confidence: 0.98` que
`contratos.py` existe para não repetir, e o gate da Fase 14 proíbe.

O que acontece HOJE com PiP, dito em voz alta para ninguém se surpreender:

    sozinha tocando          vence. "Tocando" resolve antes de o PiP importar.
    contra uma aba ATIVA
    que também toca          PERDE — `active` decide e o PiP não tem voz.

O segundo caso é justamente o que o PiP deveria ganhar, e é por ele que a
observação faz falta.

Para fechar isto basta uma observação real: duas abas com mídia, uma delas em
Picture-in-Picture. Dez segundos de uso. `scripts/ver_abas.py` acusa quando
chegar.
"""

from __future__ import annotations

from app.bridge.telemetria import uma_por_aba


def _chave(sessao) -> tuple:
    """A ordem de autoridade, do critério mais forte para o mais fraco.

    Maior vence. Cada posição é um critério, e a comparação só chega à
    seguinte quando a anterior empata — é o que permite responder "venceu por
    causa deste critério" em vez de "somou mais pontos".
    """
    return (
        # 1. IDENTIFICADA. A sessão sabe dizer O QUE está reproduzindo — nome
        #    de obra, identidade de página, ou os dois.
        #
        #    Este critério vem ANTES de "tocando", e a primeira versão deste
        #    arquivo não o tinha: eu pus "tocando" no topo e ressuscitei um bug
        #    que já custou uma medição ao vivo. Em 25/08/2026, no diagnóstico:
        #
        #        playing  pos=0,0/47,7   sem pageId, sem obra  <- a vitrine
        #        paused   pos=222/8352   com pageId, "Fight Club"
        #
        #    A vitrine da home da Netflix toca um trailer de quarenta segundos
        #    sozinha. Por "quem toca vence", ela ganhava do filme que a pessoa
        #    estava assistindo — que estava pausado justamente porque ela foi
        #    olhar o catálogo. O cartão trocava Fight Club por um trailer.
        #
        #    Uma reprodução que ninguém consegue nomear não é o que a pessoa
        #    está assistindo; é uma página que faz barulho.
        #
        #    LIMITE CONHECIDO: o YouTube não tem adapter, então uma sessão dele
        #    é sempre "não identificada" e perde para um filme PAUSADO de outro
        #    serviço. É o comportamento de hoje, não uma regressão desta fase, e
        #    o conserto é um adapter de YouTube — não um remendo aqui.
        sessao.workTitle is not None or sessao.pageId is not None,
        # 2. TOCANDO. Entre duas sessões identificadas, uma pausada não
        #    descreve o que está acontecendo agora. Nos dados, 881 instantes
        #    têm exatamente uma tocando: na maioria das vezes este critério
        #    sozinho encerra a disputa.
        sessao.tocando,
        # 3. AUDÍVEL, como PROMOÇÃO. `True` sobe; `False` e `None` valem o
        #    mesmo, porque `False` aqui significa "não sei" e não "não está".
        #    Medido: 187 de 276 abas ativas e tocando dizem `audible: False`.
        sessao.audible is True,
        # 4. ABA ATIVA. O sinal mais disponível (100% das observações) e o que
        #    isola uma sozinho na maioria dos casos — 12 de 18.
        sessao.active is True,
        # 5. JANELA EM FOCO. Existe para desempatar o caso medido de VÁRIAS
        #    abas ativas (6 de 18): duas janelas do Chrome, cada uma com a sua
        #    aba selecionada. Presente em só 29% das abas, então ele desempata
        #    quando existe e nunca exclui quem não o tem.
        sessao.windowFocused is True,
        # 6. VISÍVEL. Não é sinônimo de `active` — divergem em 416 observações.
        #    Uma aba ativa numa janela minimizada não está sendo desenhada.
        sessao.visible is True,
        # 7. QUEM MANDOU TOCAR POR ÚLTIMO. O desempate mais honesto entre duas
        #    abas que insistem em estar tocando: a pessoa apertou play numa
        #    delas depois. Negativo porque MENOR é mais recente, e a chave
        #    ordena por maior. Ausente vira -infinito: nunca vence de quem tem.
        -(sessao.msDesdeUltimoPlay if sessao.msDesdeUltimoPlay is not None else float("inf")),
        # 8. QUEM DESCREVE MELHOR. Não é sinal de atenção: é qualidade da
        #    leitura, e só entra quando tudo acima empatou. Guarda o caso
        #    medido em 25/08/2026, com duas sessões do mesmo filme na Netflix e
        #    só uma sabendo o nome — o título piscava a cada batimento.
        sessao.workTitle is not None,
        sessao.pageId is not None,
        # 9. A MAIS RECENTE. Último recurso, e existe para a resposta ser
        #    determinística: um empate que devolvesse ora uma ora outra faria o
        #    cartão oscilar sem nada ter mudado na tela.
        sessao.visto_em,
        # 10. O desempate final absoluto. Duas sessões vistas no mesmo instante
        #    são possíveis, e `sessionId` é único por construção.
        sessao.sessionId,
    )


def escolher(sessoes: list):
    """A sessão que a pessoa está assistindo. `None` quando não há nenhuma.

    Uma ABA por vez: duas sessões da mesma aba são a mesma aba, e contá-las
    duas vezes foi o que torceu o dataset inteiro da Fase 14.
    """
    candidatas = uma_por_aba(sessoes)
    if not candidatas:
        return None
    return max(candidatas, key=_chave)


def por_que(sessao, outras: list) -> str:
    """Qual critério fez esta sessão vencer aquela. Para diagnóstico.

    Existe porque "previsível" é um requisito do gate desta fase, e uma escolha
    que ninguém consegue explicar não é previsível — é só determinística. Três
    rodadas de depuração em 25/08/2026 foram gastas adivinhando por que uma aba
    vencia outra, e `/bridge/diagnostico` nasceu dessa mesma dor.
    """
    nomes = (
        "identificada", "tocando", "audivel", "aba-ativa", "janela-em-foco",
        "visivel", "play-mais-recente", "sabe-a-obra", "sabe-a-pagina",
        "visto-por-ultimo", "desempate-final",
    )
    minha = _chave(sessao)
    for outra in outras:
        if outra is sessao:
            continue
        dela = _chave(outra)
        for indice, (meu, seu) in enumerate(zip(minha, dela)):
            if meu != seu:
                return nomes[indice]
    return "unica"
