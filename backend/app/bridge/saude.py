"""Saúde das fontes — e por que as duas NÃO têm a mesma forma.

O erro que este módulo evita é de categoria: tratar as fontes como se
falhassem do mesmo jeito, dando a todas um `healthy: true`. Elas não falham do
mesmo jeito.

    SMTC          falha por AUSÊNCIA. `request_async()` pendura e não volta.
                  Medido: 8 segundos sem resposta com o Disney+ tocando.
                  Mensurável no tempo — daí `responsive`, `lastSuccess`,
                  `latency`.

    Window Title  NUNCA falha assim. Ele SEMPRE devolve um título. O modo de
                  falha dele é estar ERRADO EM SILÊNCIO — "Netflix - Home -
                  Netflix" com um filme rodando. `lastSeen` não modela nada
                  disso.

Por isso `SaudeDoWindowTitle` não tem `healthy`, e o critério de implementação
incorreta nº 16 do Master Loop trava isso: um `healthy=true` genérico faria um
título errado passar por dado fresco.

O que o Window Title tem é presença — a janela existe, ela tem título, o título
dá para limpar. **Confiabilidade semântica não mora aqui.** Ela mora nas
capabilities: quem sabe que o Max nomeia o episódio e a Netflix não nomeia nada
é `PLATAFORMAS_COM_OBRA_NA_JANELA`, e é lá que continua.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.media.now_playing import limpar_titulo_de_janela


@dataclass(frozen=True)
class SaudeDoWindowTitle:
    """Presença, e só presença.

    Repare no que NÃO existe aqui: `healthy`, `lastSeen`, `trustworthy`. Uma
    janela lida agora não é mais confiável do que uma lida há um minuto — o
    título dela é igualmente capaz de ser a home do serviço nos dois casos.
    """

    #: Existe uma janela de plataforma aberta?
    windowPresent: bool
    #: Essa janela tem título não vazio?
    titlePresent: bool
    #: A limpeza produz um nome, em vez de sobrar nada?
    parseable: bool

    @classmethod
    def de(cls, titulo: str | None) -> SaudeDoWindowTitle:
        """Deriva a presença do título cru da janela.

        `None` é "não havia janela"; string vazia é "havia janela sem título".
        Os dois casos são diferentes e o modelo os distingue.
        """
        if titulo is None:
            return cls(windowPresent=False, titlePresent=False, parseable=False)
        if not titulo.strip():
            return cls(windowPresent=True, titlePresent=False, parseable=False)
        return cls(
            windowPresent=True,
            titlePresent=True,
            parseable=bool(limpar_titulo_de_janela(titulo).strip()),
        )


@dataclass(frozen=True)
class SaudeDaSMTC:
    """Disponibilidade no tempo — que é o que esta fonte tem de específico.

    `available` e `responsive` respondem coisas diferentes, e confundir as duas
    foi o que fez o Disney+ sumir por meses: a SMTC ESTAVA disponível (o
    Windows tem a API, o módulo importa) e não estava respondendo.
    """

    #: A API existe nesta máquina? Falso fora do Windows ou sem `winsdk`.
    available: bool
    #: Está respondendo agora, ou pendurada/abandonada?
    responsive: bool
    #: Relógio monotônico da última leitura que voltou. `None` = nenhuma ainda.
    lastSuccess: float | None
    #: Duração da última leitura completa, em segundos.
    latency: float | None
    #: Prazo configurado até desistir de uma chamada.
    timeout: float

    @classmethod
    def de(cls, leitura) -> SaudeDaSMTC:
        """Deriva da `LeituraEmVoo`, que é quem já sabe tudo isso.

        Só observa. Nenhuma decisão da `LeituraEmVoo` depende desta classe, e é
        isso que mantém a Fase 3 não-regressiva.
        """
        return cls(
            available=smtc_disponivel(),
            responsive=not leitura.travada,
            lastSuccess=leitura.ultimo_sucesso,
            latency=leitura.ultima_latencia,
            timeout=type(leitura).SEGUNDOS_ATE_DESISTIR,
        )


def smtc_disponivel() -> bool:
    """A API de mídia do Windows existe nesta máquina?

    Import de verdade, e não `sys.platform`: um Windows sem o `winsdk`
    instalado responde "sim" para a plataforma e "não" para a API, e é a
    segunda resposta que interessa.
    """
    import sys

    if sys.platform != "win32":
        return False
    try:
        import winsdk.windows.media.control  # noqa: F401
    except Exception:  # noqa: BLE001 - qualquer falha de import é indisponível
        return False
    return True
