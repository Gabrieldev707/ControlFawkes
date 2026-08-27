"""Fase 16 — a ponte no sentido inverso: do ControlFawkes para dentro da aba.

Até aqui a ponte só falava para cima. A extensão observa, o host repassa, o
backend consome. Nenhum caminho existia de volta, e por isso o play/pause de
hoje é uma **tecla**: `_toggle_play_pause` foca a janela e aperta a barra de
espaço.

Isso funciona, e continua sendo o plano B. Mas tem três limites medidos:

    1. rouba o foco       focar a janela do Chrome tira o foco de onde a
                          pessoa estava. É visível e é irritante.
    2. não sabe procurar  a barra de espaço vai para a aba ATIVA, e a aba
                          ativa nem sempre é a que está tocando. Medido na
                          Fase 14: em 6 dos 18 instantes com duas abas
                          tocando havia mais de uma aba "ativa" — janelas
                          diferentes, cada uma com a sua.
    3. não sabe posição   não existe "barra de espaço" para pular para
                          1h23. `SEEK_TO` é impossível por tecla.

Comandar o `<video>` diretamente resolve os três: acerta a aba que o árbitro
escolheu, não mexe no foco de ninguém, e `currentTime = x` é uma atribuição.

## Como o comando desce, já que o host não pode ser chamado

Native Messaging é o Chrome quem inicia: ele SPAWNA o host e fala por stdio.
Ninguém de fora abre uma conexão com o host — é justamente essa a propriedade
de segurança que fez a Fase 1 escolher este transporte em vez de um WebSocket
em localhost, que qualquer página aberta alcança.

Então o host é quem pergunta:

    host  ──GET /bridge/comandos (espera até 25s)──►  ControlFawkes
                                                     (segura até haver um)
    host  ◄──────────── o comando ───────────────
    host  ──stdout──►  service worker  ──►  aba  ──►  <video>
    host  ◄──────────── o resultado ──────────────
    host  ──POST /bridge/comandos/{id}/resultado──►  ControlFawkes

A espera longa existe para o comando sair na hora em vez de esperar o próximo
ciclo. Uma consulta a cada segundo daria até um segundo de atraso num botão que
a pessoa acabou de apertar — e gastaria uma requisição por segundo para dizer
"nada" na esmagadora maioria das vezes.

## O que este módulo NÃO faz

Não decide qual aba. Isso é o árbitro (`arbitro.py`), e quem o consulta é o
dispatcher. Aqui o `tabId` chega pronto.

Não executa nada. Ele só guarda o pedido e o resultado — a execução acontece
dentro da página, que é o único lugar que tem o elemento.

E não persiste: um comando é sobre o agora. Um "pause" guardado em disco e
entregue depois de o servidor reiniciar pausaria algo que ninguém pediu.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field


#: As ações que a página sabe executar. Lista curta e fechada, pelo mesmo
#: motivo de `eventos.TIPOS`: cada uma tem quem a receba do outro lado, e uma
#: ação sem executor é uma promessa que falha em silêncio.
ACOES: frozenset[str] = frozenset({"PLAY", "PAUSE", "SEEK_TO", "SEEK_BY"})

#: Quanto o host segura a consulta antes de desistir e perguntar de novo.
#:
#: Bem abaixo do tempo em que o Chrome derruba um host silencioso, e bem acima
#: do intervalo em que uma pessoa aperta botões. Vinte e cinco segundos gastam
#: duas requisições por minuto quando não há nada acontecendo.
SEGUNDOS_DE_ESPERA = 25.0

#: Quanto o dispatcher espera o resultado antes de considerar que a ponte não
#: respondeu e cair para o plano B (a tecla).
#:
#: Curto de propósito: quem apertou o botão está olhando para a tela. Melhor
#: tentar a tecla depois de um segundo e meio do que ficar parado.
SEGUNDOS_ATE_DESISTIR = 1.5

#: Teto da fila. Se ela encher, alguém está enfileirando sem ninguém consumir —
#: o Chrome fechado, por exemplo. Guardar mil comandos para entregar todos de
#: uma vez quando ele voltar seria pior do que perdê-los.
MAXIMO_NA_FILA = 32


@dataclass(frozen=True)
class Comando:
    """Um pedido para a página, com endereço."""

    id: str
    acao: str
    #: Qual aba. Vem do árbitro, e é o que impede o comando de acertar a aba
    #: errada quando há várias tocando.
    tabId: int | None
    #: Qual reprodução. O worker confere: se a aba já trocou de sessão, o
    #: comando não é executado — pausar o episódio seguinte porque o anterior
    #: foi pedido é pior do que não pausar nada.
    sessionId: str | None
    #: Segundos. `SEEK_TO` é absoluto, `SEEK_BY` é relativo (pode ser negativo).
    valor: float | None
    criado_em: float

    def como_mensagem(self) -> dict:
        """A forma que desce pelo stdio até a extensão."""
        return {
            "protocolVersion": 1,
            "messageType": "COMANDO",
            "payload": {
                "id": self.id,
                "acao": self.acao,
                "tabId": self.tabId,
                "sessionId": self.sessionId,
                "valor": self.valor,
            },
        }


@dataclass
class Resultado:
    ok: bool
    detalhe: str | None = None


@dataclass
class FilaDeComandos:
    """Os comandos esperando para descer, e os resultados voltando.

    Em memória e só em memória, como o estado da ponte e pelo mesmo motivo:
    isto descreve o instante.
    """

    _pendentes: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(MAXIMO_NA_FILA))
    _resultados: dict = field(default_factory=dict)

    def enfileirar(
        self,
        acao: str,
        tabId: int | None,
        sessionId: str | None,
        valor: float | None = None,
    ) -> Comando | None:
        """Põe um comando na fila. `None` quando a ação não existe ou a fila encheu.

        Devolver `None` em vez de levantar é de propósito: quem chama tem um
        plano B (a tecla), e uma exceção o obrigaria a tratar como erro o que é
        apenas "por aqui não deu".
        """
        if acao not in ACOES:
            return None
        comando = Comando(
            id=uuid.uuid4().hex[:12],
            acao=acao,
            tabId=tabId,
            sessionId=sessionId,
            valor=valor,
            criado_em=time.monotonic(),
        )
        try:
            self._pendentes.put_nowait(comando)
        except asyncio.QueueFull:
            # Ninguém está consumindo — Chrome fechado, host morto. Guardar
            # para entregar tudo de uma vez depois seria pior: a pessoa
            # apertaria play e receberia dez comandos velhos junto.
            return None
        return comando

    async def proximo(self, espera: float = SEGUNDOS_DE_ESPERA) -> Comando | None:
        """O próximo comando, esperando até `espera` segundos por um.

        `None` quando o tempo acabou sem nada — e isso é resposta normal, não
        erro: o host pergunta de novo.
        """
        try:
            return await asyncio.wait_for(self._pendentes.get(), timeout=espera)
        except (TimeoutError, asyncio.TimeoutError):
            return None

    def resolver(self, id_do_comando: str, ok: bool, detalhe: str | None = None) -> bool:
        """A página respondeu. Devolve se alguém ainda esperava.

        Uma resposta pode chegar ANTES de alguém começar a esperar por ela. No
        dispatcher isso não acontece — entre `enfileirar` e `esperar` não há
        `await`, então nada consegue se meter no meio —, mas depender dessa
        coincidência é o tipo de coisa que funciona até o dia em que alguém
        põe um `await` ali. Então a resposta adiantada fica guardada.

        Guardada com TETO: um resultado que ninguém buscar é lixo, e sem teto o
        dicionário cresceria para sempre num processo que fica ligado por dias.
        """
        guardado = self._resultados.get(id_do_comando)
        resultado = Resultado(ok=ok, detalhe=detalhe)

        if guardado is None:
            self._guardar(id_do_comando, resultado)
            return False
        if isinstance(guardado, Resultado):
            # Já havia uma resposta para este id. A primeira vale.
            return False
        self._resultados.pop(id_do_comando, None)
        if guardado.done():
            # Quem esperava já desistiu e caiu para a tecla. Chegar atrasado
            # não é erro; é só tarde.
            return False
        guardado.set_result(resultado)
        return True

    def _guardar(self, id_do_comando: str, resultado: Resultado) -> None:
        """Segura uma resposta adiantada, sem deixar o dicionário crescer."""
        adiantadas = [
            chave for chave, valor in self._resultados.items()
            if isinstance(valor, Resultado)
        ]
        for chave in adiantadas[: max(0, len(adiantadas) - MAXIMO_NA_FILA + 1)]:
            self._resultados.pop(chave, None)
        self._resultados[id_do_comando] = resultado

    async def esperar(
        self, comando: Comando, ate: float = SEGUNDOS_ATE_DESISTIR,
    ) -> Resultado | None:
        """O resultado, ou `None` se a página não respondeu a tempo.

        `None` é o sinal para o plano B. Quem apertou o botão está olhando para
        a tela: melhor tentar a tecla depois de um segundo e meio do que ficar
        esperando uma resposta que talvez nunca venha.
        """
        # O futuro nasce AQUI, e não em `enfileirar`.
        #
        # Criá-lo lá exigia um laço de eventos rodando no momento de enfileirar,
        # e nem todo chamador tem um — o teste que enfileira duzentos comandos
        # para provar o teto da fila não tem. E não há corrida: entre
        # `enfileirar` e este `esperar` não existe `await`, então nenhum
        # resultado consegue chegar antes de haver quem o receba.
        guardado = self._resultados.get(comando.id)
        if isinstance(guardado, Resultado):
            # A resposta chegou antes de começarmos a esperar.
            self._resultados.pop(comando.id, None)
            return guardado
        futuro = guardado
        if futuro is None:
            futuro = asyncio.get_running_loop().create_future()
            self._resultados[comando.id] = futuro
        try:
            return await asyncio.wait_for(asyncio.shield(futuro), timeout=ate)
        except (TimeoutError, asyncio.TimeoutError):
            # Sai do dicionário para não vazar: quem responder depois disto
            # encontra a porta fechada, que é o certo.
            self._resultados.pop(comando.id, None)
            return None

    @property
    def pendentes(self) -> int:
        return self._pendentes.qsize()


#: A fila do processo. Uma só, como `estado_da_ponte` — há um ControlFawkes.
fila_de_comandos = FilaDeComandos()
