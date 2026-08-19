"""Transformar o que está tocando agora em histórico.

O laço de "tocando agora" já visita o computador uma vez por segundo. Este
gravador só olha para essa passagem e conta: enquanto o mesmo título continua
tocando, soma; quando ele sai de cena, grava o que valeu a pena.

Duas regras evitam um histórico cheio de lixo:

    Só conta o que está tocando. Pausado é o mesmo que desligado — deixar a
    Netflix parada a tarde inteira não é assistir.

    Só grava a partir de 90 segundos. Abaixo disso a pessoa estava procurando,
    não vendo, e cada troca de aba viraria uma linha no histórico.

Um trecho longo também é gravado de tempos em tempos, para um desligamento no
meio de um filme não apagar duas horas de sessão.
"""

from __future__ import annotations

from app.history.store import (
    PLATAFORMAS_FORA_DO_HISTORICO,
    SEGUNDOS_PARA_CONTAR,
    HistoryStore,
)
from app.media.now_playing import NowPlaying, _titulo_generico


# Grava a sessão em andamento de vez em quando: sem isto, fechar o servidor no
# meio de um filme perderia tudo o que foi assistido desde o início dele.
SEGUNDOS_ENTRE_GRAVACOES = 120.0

# Serviços que o controle opera mas não registra como assistidos.
#
# O Spotify continua inteiro em todo o resto: abre, controla, pausa, e aparece
# no cartão de "tocando agora" com capa e progresso. O que ele não vira é
# histórico — porque este histórico responde "o que eu estava assistindo" e "do
# que eu gosto", e música não responde nenhuma das duas.
#
# Concreto: cada faixa passa dos 90 segundos, então uma tarde de trabalho com
# música de fundo viraria dezenas de "títulos assistidos", inflando as horas e
# disputando o "mais usado" com filme. Sem contar que ninguém retoma uma música
# de onde parou, e o catálogo de filme não tem gênero para ela.
#
# O YouTube entrou aqui em 18/08/2026, a pedido, e pelas mesmas razões medidas:
#
#   Não se retoma. "Continuar assistindo" existe para voltar ao ponto de um
#   filme ou de uma série; um vlog ou um jogo ao vivo ou se assiste inteiro ou
#   não se volta a ele.
#
#   Não está no catálogo. O TMDB é catálogo de filme e série, e perguntar a ele
#   pelo nome de um vídeo devolve a capa de outra coisa — o vlog "CHEGUEI NA
#   SÍRIA" apareceu com pôster de filme. `podar_capas` existe por causa disso.
#
#   Enterrava o resto. Três vídeos de 16/08 empurraram para fora do corte de
#   "continuar assistindo" tudo o que era de 14/08, incluindo Família Soprano e
#   A Casa do Dragão.
#
# Continua inteiro em todo o resto: abre, controla, aparece em "tocando agora".
# A lista mora em `store.py`: a leitura precisa dela tanto quanto a gravação.
__all__ = ["HistoryRecorder", "PLATAFORMAS_FORA_DO_HISTORICO"]


class HistoryRecorder:
    def __init__(self, store: HistoryStore | None = None) -> None:
        self.store = store or HistoryStore()
        self._titulo: str | None = None
        self._platform = None
        self._acumulado = 0.0
        self._nao_gravado = 0.0
        self._posicao: float | None = None
        self._duracao: float | None = None
        self._episodio: str | None = None
        # A última obra que se conseguiu NOMEAR em cada serviço, nesta execução.
        #
        # Existe para o caso do Max: a janela dele publica o nome do EPISÓDIO
        # ("Members Only"), nunca o da série, e quando a SMTC pendura não sobra
        # ninguém que saiba dizer "Família Soprano". Sem isto o tempo era
        # jogado fora inteiro — a obra parava de contar no meio da sessão, sem
        # nada na tela explicando por quê.
        #
        # NÃO é palpite: só entra aqui obra que uma fonte confiável nomeou
        # nesta mesma execução, no mesmo serviço. Some quando o servidor
        # reinicia, que é quando deixa de haver continuidade para afirmar.
        self._obra_do_servico: dict[str, str] = {}

    def observar(self, atual: NowPlaying | None, intervalo: float) -> None:
        """Um instante do que está tocando. Chamado a cada volta do laço."""
        titulo = atual.title.strip() if atual and atual.title else None
        platform = atual.platform if atual else None

        # "Netflix" não é um título: é a página de catálogo aberta sem nada
        # tocando. Entrava no histórico como se fosse uma obra assistida, e
        # ainda ia parar na busca de capa e nas conquistas.
        if titulo is not None and atual is not None and _titulo_generico(
            titulo, atual.app, platform,
        ):
            titulo = None

        # Música não entra: o controle segue operando o Spotify, só não conta.
        if platform in PLATAFORMAS_FORA_DO_HISTORICO:
            titulo = None

        episodio = atual.episode if atual is not None else None

        # Leitura degradada. Com a API de mídia do Windows pendurada, o que
        # sobra é o título da janela — e numa série do Max ele é o do EPISÓDIO,
        # não o da obra. Medido no histórico real: uma tarde de Rick and Morty
        # virou quatro "títulos assistidos" com nome de episódio, um deles
        # ("Campo dos Sonhos") com o pôster do filme de 1989 que se chama igual.
        #
        # Duas saídas, e a escolha entre elas é o conserto desta rodada:
        #
        #   se o serviço já teve uma obra NOMEADA nesta execução, o tempo é
        #   dela, e este nome degradado passa a valer como episódio. É o caso
        #   do Sopranos: a SMTC disse "Família Soprano" às 2h54, pendurou, e a
        #   partir daí a janela só sabia dizer "Members Only".
        #
        #   se não houve, não se inventa obra nenhuma. O episódio NÃO vira uma
        #   linha independente — era assim que "46 Long" e "Pilot" viravam
        #   obras assistidas, e as duas estão no backup deste histórico.
        if atual is not None and not atual.trustworthy and titulo is not None:
            conhecida = self._obra_do_servico.get(platform) if platform else None
            if conhecida is not None:
                episodio, titulo = titulo, conhecida
            else:
                titulo = None

        # Uma obra nomeada por fonte confiável fica lembrada para o serviço.
        if (
            titulo is not None
            and platform is not None
            and atual is not None
            and atual.trustworthy
        ):
            self._obra_do_servico[platform] = titulo

        # Trocou de OBRA: a anterior fecha a conta agora. Trocar de EPISÓDIO
        # não fecha nada — é a mesma obra, e fechar aqui foi o que fazia o
        # tempo de uma série virar vários registros curtos.
        if titulo != self._titulo or platform != self._platform:
            self.encerrar()
            self._titulo = titulo
            self._platform = platform
            self._acumulado = 0.0
            self._nao_gravado = 0.0
            self._episodio = None

        if atual is None or titulo is None:
            return

        # Mudou o episódio dentro da mesma obra: grava o que houve ATÉ AQUI com
        # a posição da reprodução que está saindo, senão o trecho do episódio
        # anterior seria carimbado com a posição do próximo.
        if episodio != self._episodio and self._nao_gravado > 0 and self._acumulado >= SEGUNDOS_PARA_CONTAR:
            self._gravar()

        self._episodio = episodio
        self._posicao = atual.position_seconds
        self._duracao = atual.duration_seconds

        # Pausado não acumula: o tempo passa, o filme não.
        if not atual.playing:
            return

        self._acumulado += intervalo
        self._nao_gravado += intervalo

        if (
            self._acumulado >= SEGUNDOS_PARA_CONTAR
            and self._nao_gravado >= SEGUNDOS_ENTRE_GRAVACOES
        ):
            self._gravar()

    def obra_conhecida(self, platform: str | None) -> str | None:
        """A obra que uma fonte confiável nomeou neste serviço, nesta execução.

        Serve ao cartão de "tocando agora" pelo mesmo motivo que já servia ao
        histórico: a janela do Max publica o EPISÓDIO, e quando a API de mídia
        do Windows pendura não sobra ninguém que saiba dizer "Ben 10". O cartão
        mostrava só "Fame" e quem lia entendia que estava tocando algo chamado
        Fame.

        Não é palpite: só sai daqui obra que a SMTC nomeou nesta mesma
        execução, no mesmo serviço. Some quando o servidor reinicia, que é
        quando deixa de haver continuidade para afirmar.
        """
        return self._obra_do_servico.get(platform) if platform else None

    def encerrar(self) -> None:
        """Fecha a conta do título atual, se ele merecer entrar."""
        if self._titulo is None:
            return
        if self._acumulado >= SEGUNDOS_PARA_CONTAR and self._nao_gravado > 0:
            self._gravar()

    def _gravar(self) -> None:
        if self._titulo is None:
            return
        try:
            self.store.registrar(
                titulo=self._titulo,
                platform=self._platform,
                segundos=self._nao_gravado,
                posicao=self._posicao,
                duracao=self._duracao,
                episodio=self._episodio,
            )
        except Exception:  # noqa: BLE001 - histórico nunca derruba a reprodução
            return
        self._nao_gravado = 0.0
