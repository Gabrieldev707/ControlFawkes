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

from app.history.store import SEGUNDOS_PARA_CONTAR, HistoryStore
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
PLATAFORMAS_FORA_DO_HISTORICO = frozenset({"SPOTIFY"})


class HistoryRecorder:
    def __init__(self, store: HistoryStore | None = None) -> None:
        self.store = store or HistoryStore()
        self._titulo: str | None = None
        self._platform = None
        self._acumulado = 0.0
        self._nao_gravado = 0.0
        self._posicao: float | None = None
        self._duracao: float | None = None

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

        # Leitura degradada não vira histórico. Com a API de mídia do Windows
        # pendurada, o que sobra é o título da janela — e numa série ele é o do
        # EPISÓDIO, não o da obra. Medido no histórico real: uma tarde de Rick
        # and Morty virou quatro "títulos assistidos" com nome de episódio, um
        # deles ("Campo dos Sonhos") com o pôster do filme de 1989 que se chama
        # igual, e nenhum com duração, porque a janela não sabe de duração.
        #
        # Continua aparecendo no cartão e continua controlável — é para isso que
        # essa leitura existe. Só não conta como obra assistida, porque não dá
        # para afirmar qual obra é.
        if atual is not None and not atual.trustworthy:
            titulo = None

        # Trocou de título: o anterior fecha a conta agora.
        if titulo != self._titulo or platform != self._platform:
            self.encerrar()
            self._titulo = titulo
            self._platform = platform
            self._acumulado = 0.0
            self._nao_gravado = 0.0

        if atual is None or titulo is None:
            return

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
            )
        except Exception:  # noqa: BLE001 - histórico nunca derruba a reprodução
            return
        self._nao_gravado = 0.0
