"""Fase 14 — o dataset de abas simultâneas, antes de qualquer política.

O gate desta fase tem uma frase que é uma ordem, e ela é a razão do arquivo:

    Nenhuma política congelada antes dos dados.

O Master Loop está dizendo que o **MediaSessionArbiter da Fase 15 não pode ser
escrito de cabeça**. É tentador — "quem está tocando e audível e na aba ativa
vence" soa óbvio — e é exatamente assim que nasce uma regra que ninguém sabe
justificar depois. O `confidence: 0.98` de `contratos.py` nasceu assim.

Então esta fase não decide nada. Ela observa, e grava o que observou.

## O que se grava, e por quê cada campo

    tabId, windowId       QUAIS abas existem ao mesmo tempo.
    active                a aba está selecionada na janela dela?
    windowFocused         a janela dela está na frente?
    visible               a aba está sendo desenhada? Diferente de `active`:
                          uma aba ativa numa janela minimizada não é visível.
    audible               sai som DESTA aba. O Chrome sabe por aba; a Core
                          Audio do ControlFawkes só sabe por processo, e o
                          Chrome é um processo só. É o campo que desfaz a
                          limitação que `audio_activity.py` documenta.
    tabMuted, muted       mudo pela aba, e mudo pelo `<video>`. São dois botões
                          diferentes e a pessoa usa os dois.
    pictureInPicture      o vídeo saiu para a janelinha flutuante. É o caso que
                          quebra "aba ativa é quem assiste" — a aba pode estar
                          em segundo plano e a pessoa assistindo.
    playbackState         o player está tocando?
    msDesdeUltimoPlay     há quanto tempo alguém mandou tocar. O desempate mais
                          honesto entre duas abas que dizem estar tocando.
    provider              qual serviço.

## O que NÃO se grava

`href`, título de página, nome de obra, id de reprodução. A regra do projeto é
não coletar navegação, e um arquivo de diagnóstico com nome de obra e endereço
vira histórico de navegação por acidente. O `provider` é o hostname e já estava
no contrato desde a Fase 2; ele fica porque a pergunta "Netflix + YouTube" não
existe sem ele.

## Só quando há mais de uma

Uma aba sozinha não tem ambiguidade nenhuma, e gravar uma linha por segundo
para dizer isso encheria o disco com o caso que não interessa. O que a Fase 14
quer ver é o CONFLITO.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json


#: Onde o dataset mora. JSONL: uma observação por linha, que é o formato que
#: sobrevive a um processo morto no meio da escrita — um JSON único ficaria
#: truncado e ilegível inteiro.
CAMINHO_PADRAO = Path(__file__).resolve().parent.parent.parent / "data" / "bridge" / "abas.jsonl"

#: Teto de linhas. O dataset serve para ver padrão, não para guardar o ano.
MAXIMO_DE_LINHAS = 5000

#: Não grava duas observações do mesmo instante. O laço roda uma vez por
#: segundo e a maioria das voltas é idêntica à anterior — gravar todas daria
#: milhares de linhas repetidas escondendo as poucas que mudaram.
SEGUNDOS_ENTRE_OBSERVACOES = 5.0


def _retrato(sessao) -> dict:
    """Uma sessão, só com os campos que a Fase 14 quer medir."""
    return {
        "tabId": sessao.tabId,
        "windowId": sessao.windowId,
        # A sessão, cortada: é o que permite ver "a mesma aba trocou de
        # reprodução" sem guardar um identificador longo por linha.
        "sessao": sessao.sessionId[:8],
        "provider": sessao.platform,
        "playbackState": sessao.playbackState,
        "active": sessao.active,
        "windowFocused": sessao.windowFocused,
        "visible": sessao.visible,
        "audible": sessao.audible,
        "tabMuted": sessao.tabMuted,
        "muted": sessao.muted,
        "pictureInPicture": sessao.pictureInPicture,
        "msDesdeUltimoPlay": sessao.msDesdeUltimoPlay,
        "msDesdeUltimoEvento": sessao.msDesdeUltimoEvento,
    }


def uma_por_aba(sessoes: list) -> list:
    """Uma ABA, uma sessão — a mais recente vence.

    ## Por que isto existe, e o que ele salvou

    O classificador contava SESSÕES e chamava isso de abas. Quando o estado da
    ponte deixava sessões fantasma vivas na mesma aba, ele lia cada fantasma
    como uma aba a mais — e o dataset inteiro ficou contaminado.

    Medido em 26/08/2026, relendo as 1526 observações com telemetria:

        instantes com sessões repetidas na mesma aba   1078 de 1526
        maior número de sessões numa única aba         8

    E o efeito na leitura do dataset foi grosseiro:

                                    contando sessões   contando ABAS
        instantes com 2+ tocando           477               18

        `duas-tocando` era quase todo artefato. A ambiguidade que a Fase 15
    existe para resolver é vinte e seis vezes mais rara do que o número cru
    dizia — e escrever o árbitro sobre o número cru teria sido otimizar um
    problema que quase não acontece.

    A causa de fundo já foi corrigida em `EstadoDaPonte._esquecer_a_mesma_aba`,
    e por isso o dado NOVO não tem fantasma. Isto fica assim mesmo: um
    classificador que confia numa invariante mantida noutro módulo mente em
    silêncio no dia em que ela quebrar, e mentir em silêncio sobre o dataset é
    pior do que não tê-lo.

    Sem `tabId` não há aba a deduplicar, e a sessão passa como está.
    """
    por_aba: dict = {}
    for indice, sessao in enumerate(sessoes):
        chave = sessao.tabId if sessao.tabId is not None else f"sem-aba-{indice}"
        # A última vence: é a mesma ordem de `_esquecer_a_mesma_aba`, e a mais
        # recente é a que descreve o que a aba está fazendo agora.
        por_aba[chave] = sessao
    return list(por_aba.values())


def caso_de(sessoes: list) -> str:
    """O nome do cenário, para os casos que o plano lista.

    Existe para a leitura do dataset não depender de alguém reconhecer o padrão
    a olho: os oito cenários da Fase 14 têm nome, e a linha diz qual é.

    Conta ABAS e não sessões — ver `uma_por_aba` para o que essa diferença
    custou ao dataset.
    """
    sessoes = uma_por_aba(sessoes)
    if len(sessoes) < 2:
        return "uma-aba"

    servicos = {s.platform for s in sessoes}
    tocando = [s for s in sessoes if s.tocando]

    if any(s.pictureInPicture for s in sessoes):
        return "pip"
    if len(tocando) > 1:
        return "duas-tocando"
    # A que toca não é a aba ativa: o caso que quebra "aba ativa é quem vê".
    if len(tocando) == 1 and tocando[0].active is False:
        return "background-tocando"
    if len(tocando) == 1 and any(s.active and not s.tocando for s in sessoes):
        return "ativa-pausada-outra-tocando"
    if len({s.windowId for s in sessoes if s.windowId is not None}) > 1:
        return "varias-janelas"
    if len(servicos) > 1:
        return "servicos-diferentes"
    return "mesmo-servico"


@dataclass
class ColetorDeAbas:
    """Grava o que aconteceu quando havia mais de uma aba com mídia.

    NÃO decide qual vence. Se um dia esta classe ganhar um método que devolva
    "a sessão ativa", a Fase 14 virou a Fase 15 sem passar pelo gate — e a
    política terá sido congelada antes dos dados, que é a única coisa que este
    arquivo existe para impedir.
    """

    caminho: Path = CAMINHO_PADRAO
    maximo: int = MAXIMO_DE_LINHAS
    _ultima: float | None = None
    _linhas: int = 0
    _contado: bool = False

    def observar(self, sessoes: list, agora: float) -> bool:
        """Um instante. Devolve se gravou."""
        if len(sessoes) < 2:
            return False
        if (
            self._ultima is not None
            and (agora - self._ultima) < SEGUNDOS_ENTRE_OBSERVACOES
        ):
            return False
        self._ultima = agora

        linha = {
            "em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "caso": caso_de(sessoes),
            "abas": [_retrato(s) for s in sessoes],
        }
        return self._escrever(linha)

    def _contar_o_que_ja_existe(self) -> None:
        """O teto vale para o ARQUIVO, e nao para esta execucao.

        `_linhas` comecava em zero a cada processo, entao o limite de 5000 nunca
        alcancava um arquivo acumulado entre reinicios: cada restart devolvia
        outras 5000 linhas de credito. Num servidor que sobe varias vezes por
        dia, o "teto" era decorativo.
        """
        if self._contado:
            return
        self._contado = True
        try:
            with self.caminho.open(encoding="utf-8") as arquivo:
                self._linhas = sum(1 for linha in arquivo if linha.strip())
        except OSError:
            self._linhas = 0

    def _escrever(self, linha: dict) -> bool:
        try:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            self._contar_o_que_ja_existe()
            if self._linhas >= self.maximo:
                return False
            with self.caminho.open("a", encoding="utf-8") as arquivo:
                arquivo.write(json.dumps(linha, ensure_ascii=False) + "\n")
            self._linhas += 1
            return True
        except OSError:
            # Diagnóstico nunca derruba a reprodução. Mesma regra do `anotar`
            # do native host.
            return False


def resumir(caminho: Path = CAMINHO_PADRAO) -> dict[str, int]:
    """Quantas observações de cada caso o dataset tem.

    É o que responde "já dá para escrever a política da Fase 15?" — e a
    resposta é "não" enquanto os cenários do plano estiverem em zero.
    """
    contagem: dict[str, int] = {}
    try:
        with caminho.open(encoding="utf-8") as arquivo:
            for linha in arquivo:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    caso = json.loads(linha).get("caso", "?")
                except json.JSONDecodeError:
                    caso = "ilegivel"
                contagem[caso] = contagem.get(caso, 0) + 1
    except OSError:
        return {}
    return dict(sorted(contagem.items(), key=lambda par: -par[1]))
