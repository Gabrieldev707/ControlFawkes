"""O player está rodando, ou a pessoa está assistindo?

São duas perguntas, e o projeto tratava as duas como uma. `contratos.py` já
anunciava este arquivo na Fase 2: "`consumptionState` é DERIVADO — nenhuma
fonte o reporta, porque nenhuma fonte sozinha sabe. Ver `app/bridge/consumo.py`
na Fase 9."

## O bug que dá nome à fase

Medido nesta máquina: o Chrome com a sessão de áudio em `Inactive` — nenhum som
saindo — enquanto "Batman: Caped Crusader" somava um segundo por segundo até
129 minutos no catálogo. O player estava tecnicamente reproduzindo. Ninguém
estava assistindo.

`video.paused === false` responde "o elemento está reproduzindo?". Uma aba
muda, uma aba em segundo plano, uma janela esquecida: todas respondem `false` a
`paused`. Somar tempo com base nisso foi o que produziu os 129 minutos.

## Duas respostas, de propósito

    a TELA usa o estado técnico     o botão precisa dizer "pausado" quando o
                                    player está pausado, e a barra precisa
                                    andar quando ele anda. Perguntar sobre
                                    consumo aqui daria um controle que mente
                                    sobre o que o player está fazendo.

    o HISTÓRICO usa a política      somar tempo é uma afirmação sobre a
                                    PESSOA, não sobre o player.

O gate da Fase 9 é literalmente isso: "UI usa estado técnico correto.
Histórico usa política mais forte."

## Por que INDETERMINADO existe

Porque a alternativa é pior nas duas pontas. Sem forma de medir áudio — fora do
Windows, sem `pycaw`, ou com a Core Audio recusando — exigir prova de consumo
faria o histórico parar de gravar para todo mundo. Foi um erro assim que
apagou uma série inteira do Disney+: a sonda respondia `False` para quem estava
assistindo, o gravador tratava como pausado, e nada era gravado.

Então INDETERMINADO conta. O que NÃO conta é a evidência CONTRÁRIA: o player
diz que toca e a Core Audio diz que o processo está calado. Aí não é ignorância,
é contradição — e é exatamente o caso do Batman.
"""

from __future__ import annotations

from typing import Literal


#: A terceira pergunta de `contratos.py`, agora com nome e valores.
#:
#:   ASSISTINDO       há evidência positiva de consumo.
#:   NAO_ASSISTINDO   há evidência CONTRÁRIA. Não é ausência de prova.
#:   INDETERMINADO    não há como afirmar nem negar.
EstadoDeConsumo = Literal["ASSISTINDO", "NAO_ASSISTINDO", "INDETERMINADO"]


def avaliar(
    playbackState: str | None,
    audible: bool | None = None,
    muted: bool | None = None,
    audible_do_processo: bool | None = None,
) -> EstadoDeConsumo:
    """A evidência de consumo, a partir do que as fontes declararam.

    ## Os dois `audible` NÃO são a mesma evidência

    É a correção de 25/08/2026, e ela custou duas horas de histórico:

        audible              da ABA, pelo `chrome.tabs` do service worker. O
                             Chrome sabe exatamente qual aba emite som. Isto é
                             prova.

        audible_do_processo  da Core Audio, por PROCESSO. O Chrome tem dezenas
                             de sessões de áudio — uma por renderer, mais as que
                             sobraram de abas fechadas — e responder "este
                             processo está calado" é diferente de responder
                             "esta reprodução está calada". Isto é indício.

    Tratar os dois igual foi o erro. A primeira versão desta função negava
    consumo com um `False` da Core Audio, e o resultado foi **nenhum registro
    em nenhum serviço** enquanto a pessoa assistia — exatamente o defeito que
    `audio_activity.py` documenta em primeira pessoa: "respondendo False para
    quem está assistindo, o gravador tratava tudo como pausado e uma série
    inteira no Disney+ não virava um segundo de histórico".

    O `audible_do_processo` CONFIRMA e não NEGA. É assimétrico de propósito:
    um "sai som daqui" é informação positiva mesmo vindo do processo inteiro;
    um "não sai som daqui" pode ser a sonda não tendo achado a sessão certa.

    ## Então o que ainda bloqueia o bug do Batman?

    `playbackState`, e o caminho por onde ele é apurado — não um veto de áudio.

    O Batman somou 129 minutos porque a leitura degradada CHUTAVA `playing=True`
    ("a janela está aberta, logo a pessoa está assistindo"). O conserto foi
    `da_janela(tocando=processo_esta_tocando(...))`: com o processo calado, a
    leitura devolve `playing=False`, e "pausado não acumula" faz o resto. Esse
    conserto está intacto e é onde a Core Audio de fato funciona — ali ela
    responde "o Chrome está tocando ALGUMA coisa?", que é uma pergunta que o
    processo consegue responder.

    O que esta função NÃO pode fazer é usar o mesmo sinal para responder "ESTA
    reprodução está sendo assistida?". É outra pergunta, e nenhuma fonte de
    áudio disponível hoje a responde com precisão suficiente para negar.
    """
    # Não está tocando: o resto da evidência não importa. Pausado é pausado,
    # com som ou sem som, e "ended" é o fim.
    if playbackState != "playing":
        return "NAO_ASSISTINDO"

    # NENHUM sinal de áudio nega. Os dois só confirmam.
    #
    # Esta linha foi escrita três vezes em 25/08/2026, e as duas primeiras
    # quebraram o histórico inteiro:
    #
    #   1. `audible_do_processo is False` negava. A Core Audio responde por
    #      PROCESSO, o Chrome tem dezenas de sessões de áudio, e o resultado foi
    #      nenhum registro em nenhum serviço por duas horas.
    #
    #   2. `audible is False` negava. Parecia seguro — vem do `chrome.tabs`, o
    #      navegador sabe qual aba emite som. Medido com o diagnóstico ao vivo,
    #      com INVINCIBLE tocando e visível no cartão:
    #
    #          PRIME_VIDEO playing | pos=1045.2/3029.0 | active=False | audible=False
    #
    #      A aba dizia estar calada enquanto a pessoa assistia. `sender.tab` é
    #      um retrato do momento da conexão, e `audible` ali não é confiável.
    #
    # O padrão é o mesmo nas duas: um sinal de áudio foi promovido a prova sem
    # ser validado, e cada promoção custou o histórico inteiro. Áudio é indício.
    if audible is True or audible_do_processo is True:
        return "ASSISTINDO"

    # Tudo o mais — inclusive os dois dizendo `False` — cai aqui. Ausência de
    # prova não é prova de ausência, e este é o lado seguro do erro: contar
    # tempo demais é ruim; apagar o histórico de quem está assistindo é pior, e
    # já aconteceu três vezes.
    #
    # `muted` também não nega: legenda com som desligado é forma legítima de
    # assistir.
    return "INDETERMINADO"


def conta_como_assistido(estado: EstadoDeConsumo) -> bool:
    """O histórico deve somar este intervalo?

    INDETERMINADO conta. Ver a docstring do módulo: exigir prova positiva faria
    o histórico parar de gravar em toda máquina onde a Core Audio não responde,
    e esse erro já custou uma série inteira do Disney+.
    """
    return estado != "NAO_ASSISTINDO"
