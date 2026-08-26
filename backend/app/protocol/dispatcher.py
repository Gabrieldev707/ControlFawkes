import asyncio
from dataclasses import replace
import json
import time

from fastapi import WebSocket
from pydantic import TypeAdapter, ValidationError

from app.schemas.auth import (
    AuthMessage,
    AuthResultMessage,
    PairDeviceMessage,
    PairResultMessage,
)
from app.schemas.ws import (
    ClientMessage,
    CommandResultMessage,
    NeedsPlatformMessage,
    NavigationCommandData,
    HeartbeatMessage,
    NowPlayingMessage,
    NowPlayingSession,
    TitleAvailabilityData,
    MediaLinkCommandData,
    ErrorCode,
    ErrorMessage,
    HelpCommandData,
    KeyboardCommandData,
    KeyboardKeyMessage,
    KeyboardTextMessage,
    MediaCommandData,
    MediaControlMessage,
    PointerClickMessage,
    PointerCommandData,
    PointerDoubleClickMessage,
    PointerDownMessage,
    PointerMoveMessage,
    PointerRightClickMessage,
    PointerScrollMessage,
    PointerUpMessage,
    Platform,
    PlatformCommandData,
    PlatformSelectedMessage,
    SearchMediaCommandData,
    SearchMediaMessage,
    StateUpdateMessage,
    TextCommandMessage,
    VolumeCommandData,
    VolumeDeltaMessage,
    VolumeGetMessage,
    VolumeMuteToggleMessage,
    VolumeSetMessage,
)
from app.commands.parser import (
    HELP_COMMANDS,
    PLATFORM_LABELS,
    NeedsPlatformIntent,
    MediaControlIntent,
    OpenMediaLinkIntent,
    OpenPlatformIntent,
    SearchMediaIntent,
    ShowHelpIntent,
    UnknownIntent,
    VolumeControlIntent,
    parse_command,
)
from app.security.device_store import DeviceStore
from app.security.origins import is_origin_allowed
from app.security.pairing import PairingService
from app.platforms.launcher import PlatformLauncher
from app.platforms.registry import open_only_platforms, suggested_search_platforms
from app.platforms.search import MediaSearchLauncher
from app.media.actions import MEDIA_ACTIONS, MEDIA_ACTION_LABELS
from app.media.now_playing import (
    LeituraEmVoo,
    WindowsNowPlayingReader,
    _titulo_generico,
    da_janela,
    limpar_titulo_de_janela,
)
from app.media.session import WindowsMediaSessionDetector
from app.media.windows_adapter import WindowsMediaAdapter
from app.schemas.volume import VOLUME_ACTIONS
from app.windows.volume import WindowsVolumeAdapter, WindowsVolumeError
from app.windows.app_volume import (
    SCOPE_LABELS,
    AppVolumeUnavailable,
    WindowsAppVolumeAdapter,
)
from app.windows.audio_activity import processo_esta_tocando
from app.bridge.consumo import EstadoDeConsumo, avaliar as avaliar_consumo
from app.bridge.estado import FOLGA_DA_DURACAO, EstadoDaPonte, estado_da_ponte
from app.bridge.saude import smtc_disponivel
from app.bridge.comandos import fila_de_comandos
from app.bridge.telemetria import ColetorDeAbas
from app.media.fusao import fundir_com_a_ponte
from app.media.identidade import como_temporada_e_episodio
from app.windows.focus import WindowFocuser, platform_of
from app.windows.screen import WindowCapture, ponto_na_tela
from app.profiles.store import ProfileStore
from app.history.recorder import HistoryRecorder
from app.catalog.tmdb import PLATAFORMAS_COM_CATALOGO, TmdbCatalog
from app.input.pointer import PointerRateLimiter, WindowsPointerAdapter
from app.schemas.pointer import POINTER_ACTIONS
from app.schemas.screen import (
    SCREEN_ACTIONS,
    ProfileSelectMessage,
    ScreenCommandData,
    ScreenTapMessage,
)
from app.input.keyboard import WindowsKeyboardAdapter
from app.schemas.keyboard import KEYBOARD_ACTIONS
from app.schemas.navigation import (
    NAVIGATION_ACTIONS,
    NAVIGATION_KEYS,
    NAVIGATION_LABELS,
    REPEATABLE_ACTIONS,
    NavigationMessage,
)
from app.intelligence.service import IntentFallbackService, build_intent_service_from_env
from app.protocol.rate_limits import (
    MAX_CONNECTIONS,
    MAX_MESSAGES_PER_SECOND,
    MAX_NAVIGATION_PER_SECOND,
    MAX_NON_REPEATABLE_PER_SECOND,
    message_limiter,
    navigation_limiter,
    non_repeatable_navigation_limiter,
)


# Um segundo dá reação imediata ao pausar sem custar nada: a leitura é local
# e só vira mensagem quando algo muda.
NOW_PLAYING_INTERVAL_SECONDS = 1.0

# Bem abaixo do tempo que um roteador leva para descartar conexão ociosa, e
# raro o bastante para não pesar: são poucos bytes a cada dez segundos.
HEARTBEAT_INTERVAL_SECONDS = 10.0

# A contagem local do celular acumula erro; a cada 15s ela é ancorada de
# novo no valor real, sem virar um envio por segundo.
POSITION_RESYNC_SECONDS = 15.0

# A Core Audio custa COM + enumeração de todas as sessões de áudio. A resposta
# não muda a cada segundo, e o laço roda uma vez por segundo — perguntar toda
# volta seria pagar caro por um dado que se repete. Ver `_audivel_agora`.
SEGUNDOS_ENTRE_SONDAS_DE_AUDIO = 5.0

WS_POLICY_VIOLATION = 1008
WS_TRY_AGAIN_LATER = 1013

KNOWN_CLIENT_TYPES = {
    "AUTH",
    "PAIR_DEVICE",
    "PLATFORM_SELECTED",
    "TEXT_COMMAND",
    "SEARCH_MEDIA",
    *MEDIA_ACTIONS,
    *VOLUME_ACTIONS,
    *POINTER_ACTIONS,
    *KEYBOARD_ACTIONS,
    *NAVIGATION_ACTIONS,
    *SCREEN_ACTIONS,
}


def _sem_posicao(mensagem: dict | None) -> dict | None:
    """A mensagem sem o campo que muda sozinho a cada segundo."""
    if mensagem is None:
        return None
    sessao = mensagem.get("session")
    if not isinstance(sessao, dict):
        return mensagem
    return {**mensagem, "session": {k: v for k, v in sessao.items() if k != "positionSeconds"}}


class Dispatcher:
    # Acima do teto do touchpad (60/s), para não atrapalhar o uso legítimo.
    MAX_MESSAGES_PER_SECOND = MAX_MESSAGES_PER_SECOND
    MAX_CONNECTIONS = MAX_CONNECTIONS
    # Auto-repeat confortável ao segurar a seta, sem virar inundação.
    MAX_NAVIGATION_PER_SECOND = MAX_NAVIGATION_PER_SECOND
    # Confirmar/voltar: no máximo ~3 por segundo, contra toque duplo acidental.
    MAX_NON_REPEATABLE_PER_SECOND = MAX_NON_REPEATABLE_PER_SECOND

    def __init__(
        self,
        device_store: DeviceStore | None = None,
        pairing_service: PairingService | None = None,
        platform_launcher: PlatformLauncher | None = None,
        media_search_launcher: MediaSearchLauncher | None = None,
        media_adapter: WindowsMediaAdapter | None = None,
        media_session_detector: WindowsMediaSessionDetector | None = None,
        volume_adapter: WindowsVolumeAdapter | None = None,
        pointer_adapter: WindowsPointerAdapter | None = None,
        pointer_rate_limiter: PointerRateLimiter | None = None,
        keyboard_adapter: WindowsKeyboardAdapter | None = None,
        app_volume_adapter: WindowsAppVolumeAdapter | None = None,
        window_focuser: WindowFocuser | None = None,
        window_capture: WindowCapture | None = None,
        profile_store: ProfileStore | None = None,
        history_recorder: HistoryRecorder | None = None,
        catalog: TmdbCatalog | None = None,
        now_playing_reader: WindowsNowPlayingReader | None = None,
        message_rate_limiter: PointerRateLimiter | None = None,
        navigation_rate_limiter: PointerRateLimiter | None = None,
        intent_service: IntentFallbackService | None = None,
        bridge_state: EstadoDaPonte | None = None,
    ) -> None:
        self.device_store = device_store or DeviceStore()
        self.pairing_service = pairing_service or PairingService(self.device_store)
        self.platform_launcher = platform_launcher or PlatformLauncher()
        self.media_search_launcher = media_search_launcher or MediaSearchLauncher()
        self.media_adapter = media_adapter or WindowsMediaAdapter()
        self.media_session_detector = media_session_detector or WindowsMediaSessionDetector()
        self.volume_adapter = volume_adapter or WindowsVolumeAdapter()
        self.pointer_adapter = pointer_adapter or WindowsPointerAdapter()
        self.pointer_rate_limiter = pointer_rate_limiter or PointerRateLimiter()
        self.keyboard_adapter = keyboard_adapter or WindowsKeyboardAdapter()
        self.app_volume_adapter = (
            app_volume_adapter if app_volume_adapter is not None
            else WindowsAppVolumeAdapter()
        )
        self.window_focuser = window_focuser or WindowFocuser()
        self.window_capture = window_capture or WindowCapture()
        self.profile_store = profile_store or ProfileStore()
        self.history_recorder = history_recorder or HistoryRecorder()
        self.catalog = catalog if catalog is not None else TmdbCatalog()
        self.now_playing_reader = now_playing_reader or WindowsNowPlayingReader(
            window_title_reader=self.window_focuser.media_window_title,
        )
        # Capa da mídia atual, por id. Fica em memória e some com o processo:
        # é enfeite de tela, não dado que mereça disco.
        self.thumbnails: dict[str, bytes] = {}
        self._leitura = LeituraEmVoo(self.now_playing_reader)
        # Pôster por título, incluindo o "não achei". Some com o processo.
        self._posters: dict[tuple[str, Platform | None], str | None] = {}
        self._posters_em_busca: set[tuple[str, Platform | None]] = set()
        self.message_rate_limiter = message_rate_limiter or message_limiter()
        self.navigation_rate_limiter = navigation_rate_limiter or navigation_limiter()
        self.navigation_repeat_guard = non_repeatable_navigation_limiter()
        self.intent_service = intent_service or build_intent_service_from_env()
        # O MESMO objeto que a rota `/bridge/eventos` alimenta. Injetável para
        # que teste nenhum dependa do singleton do módulo.
        self.bridge_state = bridge_state if bridge_state is not None else estado_da_ponte
        # Última resposta da Core Audio, e quando ela veio. Ver `_audivel`.
        self._audivel: bool | None = None
        self._audivel_em: float | None = None
        # Fase 14: observa abas simultâneas e grava. Não decide nada — quem
        # decide é a Fase 15, e ela não pode ser escrita antes destes dados.
        self._coletor = ColetorDeAbas()
        #: Falhas de histórico já reportadas, para não afogar o terminal.
        self._falhas_do_historico: set[tuple[str, str, str]] = set()
        #: Tarefas de pôster em voo. Ver `_poster_para`.
        self._buscas_de_poster: set[asyncio.Task] = set()
        #: Temporada por (obra, número do episódio, nome do episódio). Guarda
        #: inclusive o "não deu para saber": a consulta custa seis requisições.
        self._temporadas: dict[tuple, int | None] = {}
        self._temporadas_em_busca: set[tuple] = set()
        #: (última duração vista, já cresceu?) por obra. Ver
        #: `_sem_duracao_de_buffer`.
        self._duracoes: dict[tuple, tuple[float, bool]] = {}
        self._client_adapter = TypeAdapter(ClientMessage)
        self._authenticated: dict[WebSocket, str] = {}
        self._held_pointer_buttons: set[WebSocket] = set()
        self._connections: set[WebSocket] = set()
        self._now_playing_task: asyncio.Task | None = None
        self._last_now_playing: dict | None = None

    async def startup(self) -> None:
        self.pairing_service.initialize()
        if self._now_playing_task is None:
            # Passa a régua de limpeza atual sobre o histórico antigo: sem
            # isto, uma melhoria na limpeza de título deixa para sempre duas
            # linhas do mesmo filme, cada uma com um pedaço do tempo.
            try:
                self.history_recorder.store.consolidar(limpar_titulo_de_janela)
                # E junta "X: Volume 3" em "X" quando X é uma série do mesmo
                # serviço. `consolidar` não alcança isso: "Volume 3" não é
                # ruído de navegador, é texto que a Amazon põe no nome da aba,
                # e nenhum limpador genérico tem como saber que aquilo não é a
                # obra. Ver `unificar_empacotamento` para a regra estreita —
                # inclusive por que "Kill Bill: Volume 1" não é tocado.
                self.history_recorder.store.unificar_empacotamento()
                # E tira as capas que o catálogo não tinha como acertar. Filtrar
                # na leitura escondia a capa errada da tela, mas ela continuava
                # no arquivo — e enquanto estiver lá, a busca de capa considera
                # o título já resolvido e nunca tenta de novo.
                self.history_recorder.store.podar_capas()
            except Exception:  # noqa: BLE001 - nunca impede o servidor de subir
                pass
            self._now_playing_task = asyncio.create_task(self._watch_now_playing())

    async def shutdown(self) -> None:
        # Fecha a conta do que estava tocando: sem isto, o último trecho de uma
        # sessão longa se perderia no desligamento.
        try:
            self.history_recorder.encerrar()
        except Exception:  # noqa: BLE001
            pass
        if self._now_playing_task is not None:
            self._now_playing_task.cancel()
            self._now_playing_task = None

    async def _watch_now_playing(self) -> None:
        """Empurra o que está tocando para quem já se autenticou.

        Só quando muda: reenviar o mesmo estado a cada segundo gastaria uma
        mensagem por segundo por dispositivo para não dizer nada. A posição
        segue no celular, que conta sozinho a partir do último valor.
        """
        desde_o_ultimo_sinal = 0.0
        desde_a_ultima_posicao = 0.0
        while True:
            try:
                await asyncio.sleep(NOW_PLAYING_INTERVAL_SECONDS)

                # Sem ninguém conectado o laço continua lendo, só não fala.
                # Antes ele pulava tudo, e o histórico só existia enquanto o
                # celular estivesse com a página aberta — ou seja, justamente
                # quando ninguém estava assistindo de verdade.
                if not self._authenticated:
                    try:
                        await self._read_now_playing(contar=True)
                    except Exception as erro:  # noqa: BLE001
                        self._anotar_falha_da_leitura(erro)
                    continue

                desde_o_ultimo_sinal += NOW_PLAYING_INTERVAL_SECONDS
                if desde_o_ultimo_sinal >= HEARTBEAT_INTERVAL_SECONDS:
                    desde_o_ultimo_sinal = 0.0
                    await self._broadcast(HeartbeatMessage().model_dump())

                # O que está tocando vem depois e num try próprio: uma falha
                # de mídia não pode calar o batimento, que é justamente o que
                # prova ao celular que a conexão está viva.
                try:
                    mensagem = await self._read_now_playing(contar=True)
                except Exception as erro:  # noqa: BLE001
                    self._anotar_falha_da_leitura(erro)
                    continue

                desde_a_ultima_posicao += NOW_PLAYING_INTERVAL_SECONDS
                if not self._vale_enviar(mensagem, desde_a_ultima_posicao):
                    continue
                desde_a_ultima_posicao = 0.0
                self._last_now_playing = mensagem
                await self._broadcast(mensagem)
            except asyncio.CancelledError:
                raise
            except Exception as erro:  # noqa: BLE001 - o laço não pode morrer
                self._anotar_falha_da_leitura(erro)
                continue

    def _vale_enviar(self, mensagem: dict, desde_a_ultima_posicao: float) -> bool:
        """Manda quando algo muda de verdade, não quando o relógio anda.

        A posição avança a cada segundo, então comparar a mensagem inteira
        fazia disparar um envio por segundo por dispositivo — exatamente o que
        este laço dizia evitar. Quem conta os segundos é o celular, a partir do
        último valor recebido.

        A ressincronização periódica existe porque a contagem local acumula
        erro: sem ela, uma sessão de duas horas termina com a barra em outro
        lugar do filme.
        """
        if _sem_posicao(mensagem) != _sem_posicao(self._last_now_playing):
            return True
        return desde_a_ultima_posicao >= POSITION_RESYNC_SECONDS

    async def _read_now_playing(self, contar: bool = False) -> dict:
        """A leitura atual. Com `contar`, esta passagem entra no histórico.

        A contagem fica presa à volta do laço, e não a toda chamada: o cartão
        também é lido quando um celular se conecta, e cada conexão somaria
        segundos que ninguém assistiu.
        """
        atual = await self._leitura.ler()
        if atual is None and (self._leitura.travada or not smtc_disponivel()):
            # A SMTC não respondeu. Em vez de dizer "nada tocando" e desligar
            # os controles junto, diz o que a janela aberta mostra.
            #
            # `travada` OU `não disponível`, e a segunda metade faltava.
            # `saude.py` já separava as duas — "a SMTC ESTAVA disponível (o
            # Windows tem a API, o módulo importa) e não estava respondendo" —
            # mas esta condição só conhecia a primeira.
            #
            # Consequência medida em 25/08/2026: com o servidor subido pelo
            # Python do sistema, sem `winsdk` instalado, `read()` devolvia None
            # na hora (ImportError engolido), a chamada nunca chegava a pendurar,
            # `travada` ficava False — e o socorro não entrava. Resultado: nada
            # tocando, nunca, e o histórico não crescia um segundo, sem nenhum
            # erro em lugar nenhum. Três reinícios do servidor não mudaram nada,
            # porque não era o servidor.
            #
            # Uma máquina sem `winsdk` é o mesmo caso de uma com a SMTC
            # pendurada para sempre. A janela continua sabendo o que está aberto.
            janela = self.window_focuser.media_window()
            if janela is not None:
                atual = da_janela(
                    janela.title,
                    platform_of(janela),
                    # Do processo da janela, e não da plataforma: a Netflix
                    # instalada como aplicativo toca no Edge, e as abertas no
                    # navegador tocam no Chrome. Quem sabe qual é a janela.
                    tocando=processo_esta_tocando(janela.process),
                )

        # Fase 8: o tempo medido dentro da página vence o da SMTC quando ele
        # está fresco. Aqui, e não depois do `contar`, porque o histórico
        # precisa da posição BOA — era essa a diferença entre gravar
        # `posicao 391` e gravar os 2974 segundos que a ponte já sabia.
        atual = fundir_com_a_ponte(atual, self.bridge_state)

        # A temporada entra ANTES de o histórico contar.
        #
        # Ela era acrescentada só na mensagem do cartão, e o gravador recebia o
        # `atual` cru — então "continuar assistindo" ficava com "E1 · Pilot"
        # enquanto o cartão dizia "T1 E1 · Pilot". A mesma leitura contando duas
        # histórias diferentes conforme a tela.
        atual = self._com_temporada(atual)
        atual = self._sem_duracao_de_buffer(atual)

        # Fase 14 — o dataset. Só grava quando há mais de uma aba com mídia,
        # que é o único caso em que existe ambiguidade a estudar.
        try:
            self._coletor.observar(self.bridge_state.vivas(), time.monotonic())
        except Exception:  # noqa: BLE001 - telemetria nunca cala o cartão
            pass

        if contar:
            try:
                self.history_recorder.observar(
                    atual, NOW_PLAYING_INTERVAL_SECONDS, self._consumo(atual),
                )
            except Exception as erro:  # noqa: BLE001 - histórico nunca cala o cartão
                # Engolir CONTINUA certo — uma falha de histórico não pode
                # derrubar o cartão nem o laço. O que estava errado era engolir
                # em SILÊNCIO.
                #
                # Custou duas paradas completas em 25/08/2026, e nenhuma das
                # duas deixou rastro: um `NameError` de import faltando, e uma
                # política de consumo negando tudo. Nos dois casos o histórico
                # parou de gravar por horas e o único sintoma foi um arquivo que
                # não crescia. Um traceback aqui teria respondido as duas em
                # cinco segundos.
                self._anotar_falha_do_historico(erro)

        if atual is None:
            return NowPlayingMessage(session=None).model_dump()

        if atual.thumbnail and atual.thumbnail_id:
            self.thumbnails[atual.thumbnail_id] = atual.thumbnail
            # Duas capas bastam: a atual e a anterior, para o celular que ainda
            # está baixando a de antes não receber 404.
            for antigo in list(self.thumbnails)[:-2]:
                self.thumbnails.pop(antigo, None)

        # A obra vem do histórico quando a leitura só soube o episódio.
        #
        # Medido com Ben 10 no Max: a janela publica "⁨Fame⁩ • HBO Max", e o Max
        # nunca publica o nome da série. Se a SMTC já nomeou "Ben 10" nesta
        # execução, o cartão tem como mostrar OS DOIS em vez de escolher — que
        # é a mesma correção que o histórico já tinha recebido.
        titulo, episodio, titulo_e_obra = atual.title, atual.episode, atual.trustworthy
        if not atual.trustworthy:
            lembrada = self.history_recorder.obra_conhecida(atual.platform)
            if lembrada is not None:
                titulo, episodio, titulo_e_obra = lembrada, atual.title, True

        return NowPlayingMessage(session=NowPlayingSession(
            title=titulo,
            episode=episodio,
            artist=atual.artist,
            app=atual.app,
            platform=atual.platform,
            playing=atual.playing,
            positionSeconds=atual.position_seconds,
            durationSeconds=atual.duration_seconds,
            positionStale=atual.position_stale,
            titleIsWork=titulo_e_obra,
            thumbnailId=atual.thumbnail_id,
            posterUrl=self._poster_para(atual, titulo, titulo_e_obra),
            historyRevision=self.history_recorder.revisao,
        )).model_dump()

    def _sem_duracao_de_buffer(self, atual):
        """Uma duração que CRESCE é borda de buffer, e não a duração da obra.

        ## O que se mediu

        Disney+, com Demolidor: Renascido tocando, oito leituras seguidas do
        diagnóstico ao vivo em 26/08/2026:

            660,8 → 676,8 → 692,8 → 700,8 → 708,8 → 732,8 → 740,8 → 748,8

        Sempre alguns segundos à frente da posição, sempre subindo. Não é um
        vídeo de onze minutos: é MSE. O player monta o vídeo por segmentos e
        `video.duration` reporta a borda do BUFFER enquanto o resto não chegou.

        Na tela isso é grosseiro e constante: a barra fica sempre quase cheia e
        um episódio de cinquenta minutos se anuncia como se estivesse acabando.

        ## Por que AQUI, e não na ponte

        Porque o número chega pelas DUAS fontes. A SMTC do Chrome publica a
        linha do tempo do mesmo `<video>` que a extensão observa — então
        guardar só a ponte deixava a SMTC entregar o mesmo valor pela outra
        porta, que foi exatamente o que se mediu depois do primeiro conserto.

        Este é o ponto onde o número final existe, seja qual for a fonte que o
        supriu. Uma verdade, um lugar.

        ## Por que crescer é a prova, e o tamanho não é

        A primeira tentativa cortou por duração pequena — "menos de 90 segundos
        é prévia". Errada por dois lados: suprimia reprodução de verdade no
        primeiro minuto, quando o buffer ainda é curto, e não pegava o caso
        medido, que já passava de 250 segundos.

        Uma duração que aumenta não pode ser a duração de nada. Uma que fica
        parada pode ser — e é o que a Netflix publica desde o começo, que é por
        que só ela estava certa.
        """
        if atual is None or atual.duration_seconds is None:
            return atual

        chave = (atual.platform, atual.title)
        anterior = self._duracoes.get(chave)
        cresceu = (
            anterior is not None
            and atual.duration_seconds - anterior[0] > FOLGA_DA_DURACAO
        )
        # Gruda: depois que a duração se provou borda de buffer, ela não se
        # redime ao parar de crescer — o vídeo terminou de baixar, e o número
        # pode até estar certo, mas quem já mentiu não volta a ser fonte sem
        # outra prova.
        suspeita = cresceu or (anterior is not None and anterior[1])
        self._duracoes[chave] = (atual.duration_seconds, suspeita)
        # Não deixa crescer para sempre: uma entrada por obra vista.
        if len(self._duracoes) > 64:
            self._duracoes.pop(next(iter(self._duracoes)), None)

        return replace(atual, duration_seconds=None) if suspeita else atual

    def _com_temporada(self, atual):
        """"E1 · Pilot" vira "T1 E1 · Pilot" — e "Ozymandias" vira "T5 E14".

        ## Por que o catálogo, e não o serviço

        Nenhum serviço publica as duas coisas. Medido:

            Netflix                 "E1" — falta a temporada, e ela não está em
                                    lugar nenhum da página
            Max, Prime, Disney+     só o NOME do episódio, sem número nenhum

        O catálogo conhece a série inteira, e o nome do episódio costuma isolar
        uma linha só. Achada a linha, temporada e número vêm juntos — então o
        mesmo lookup serve para os dois casos, e vale para TODO serviço, não só
        o que tem adapter.

        Ver `TmdbCatalog.numeros_do_episodio`, inclusive para quando ele se
        recusa a responder — que é o que separa isto de um palpite.

        ## Fora do laço

        A consulta custa uma requisição por temporada. Ela roda uma vez por
        episódio, em segundo plano, e a resposta fica guardada — inclusive o
        "não deu para saber". O cartão a usa a partir da volta seguinte, que
        chega em um segundo.
        """
        if atual is None or self.catalog is None or not self.catalog.enabled:
            return atual
        # Sem obra confiável não há série para procurar, e sem nada do episódio
        # não há o que isolar.
        if not atual.trustworthy or not atual.title:
            return atual

        sessao = self.bridge_state.atual_de(atual.platform)
        numero = sessao.episodeNumber if sessao is not None else None
        # O nome do episódio vem da ponte quando há adapter, e da janela quando
        # não há — que é o caso de quatro dos cinco serviços.
        nome = (sessao.episodeTitle if sessao is not None else None) or atual.episode
        if numero is None and not nome:
            return atual

        # A temporada já veio publicada: não há o que descobrir, e perguntar
        # gastaria seis requisições para confirmar o que já se sabe.
        #
        # Duas formas de já se saber, e as duas contam: o serviço declarou o
        # número, ou o rótulo do episódio já começa por "T5". A segunda cobre
        # inclusive o que chegou pela janela, onde não há campo estruturado
        # nenhum para consultar.
        if sessao is not None and sessao.seasonNumber is not None:
            return atual
        ja_tem = como_temporada_e_episodio(nome) if nome else None
        if ja_tem is not None and ja_tem.startswith("T"):
            return atual

        duracao = atual.duration_seconds
        chave = (atual.title, numero, nome)
        if chave in self._temporadas:
            achado = self._temporadas[chave]
            return atual if achado is None else replace(
                atual, episode=self._rotulo_do_episodio(achado, nome),
            )

        if chave not in self._temporadas_em_busca:
            self._temporadas_em_busca.add(chave)
            tarefa = asyncio.create_task(self._buscar_temporada(chave, duracao))
            self._buscas_de_poster.add(tarefa)
            tarefa.add_done_callback(self._buscas_de_poster.discard)
        return atual

    @staticmethod
    def _rotulo_do_episodio(numeros: tuple[int, int], nome: str | None) -> str:
        """"T5 E14 · Ozymandias" — e sem o nome quando ele era só "E1".

        O nome do episódio pode ser o próprio rótulo que veio do serviço, e
        repetir "E1" depois de "T1 E1" diria a mesma coisa duas vezes.
        """
        temporada, episodio = numeros
        rotulo = f"T{temporada} E{episodio}"
        if not nome or como_temporada_e_episodio(nome) is not None:
            return rotulo
        return f"{rotulo} · {nome}"

    async def _buscar_temporada(self, chave: tuple, duracao: float | None) -> None:
        titulo, numero, nome = chave
        try:
            # Guarda inclusive o "não deu para saber": sem isso, uma série que o
            # catálogo não isola seria consultada a cada volta do laço, e são
            # seis requisições por consulta.
            self._temporadas[chave] = await self.catalog.numeros_do_episodio(
                titulo, nome, numero, duracao,
            )
        except Exception:  # noqa: BLE001 - temporada é detalhe, nunca motivo de erro
            self._temporadas[chave] = None
        finally:
            self._temporadas_em_busca.discard(chave)

    def _anotar_falha_da_leitura(self, erro: BaseException) -> None:
        """A leitura de mídia falhando vai para o terminal, uma vez por tipo.

        O `except` que engolia isto em silêncio é o mesmo padrão que já custou
        dois apagões em 25/08/2026 — e o conserto daquele dia cobriu só a
        gravação do histórico. Uma falha na FUSÃO, no catálogo ou na capa
        continuava invisível, e o sintoma seria idêntico: o cartão para de
        atualizar e nada aparece em lugar nenhum.

        Engolir continua certo: o laço não pode morrer. Calar é que não.
        """
        self._anotar_uma_vez("leitura", "o cartao parou de atualizar", erro)

    def _anotar_falha_do_historico(self, erro: BaseException) -> None:
        """A falha vai para o terminal, uma vez por tipo.

        Uma vez por TIPO e não uma vez por falha: o laço roda uma vez por
        segundo, e um defeito permanente imprimiria 3600 tracebacks por hora —
        que é outra forma de esconder, por afogamento.

        E não é log estruturado nem arquivo: enquanto o projeto imprime o
        caminho do toque no terminal (ver `_clicar_na_janela`), este é o lugar
        onde quem está depurando já olha.
        """
        self._anotar_uma_vez(
            "historico", "o historico PAROU de crescer", erro,
        )

    def _anotar_uma_vez(self, area: str, consequencia: str, erro: BaseException) -> None:
        """Uma vez por TIPO de falha, e não uma por ocorrência.

        O laço roda uma vez por segundo: um defeito permanente imprimiria 3600
        tracebacks por hora, que é outra forma de esconder — por afogamento.
        """
        import traceback

        assinatura = (area, type(erro).__name__, str(erro)[:200])
        if assinatura in self._falhas_do_historico:
            return
        self._falhas_do_historico.add(assinatura)
        print(
            f"[{area}] falhou e {consequencia}: {type(erro).__name__}: {erro}",
            flush=True,
        )
        traceback.print_exc()

    def _consumo(self, atual) -> EstadoDeConsumo:
        """A política da Fase 9 para esta passagem do laço.

        A TELA continua recebendo `atual.playing`, que é o estado técnico do
        player — é o que faz o botão dizer "pausado" quando o player está
        pausado. Só o HISTÓRICO passa por aqui. Duas respostas da mesma
        leitura, que é literalmente o gate desta fase.
        """
        if atual is None:
            return "NAO_ASSISTINDO"
        # A sessão DESTE serviço: pedir "a que vence no geral" e depois
        # recusá-la por ser de outro serviço fazia o `muted` e o `audible` da
        # Netflix sumirem sempre que o YouTube falava por último.
        sessao = self.bridge_state.atual_de(atual.platform)
        mudo = sessao.muted if sessao is not None else None
        # As duas evidências de áudio vão SEPARADAS, e não fundidas numa só.
        # A da aba nega; a do processo só confirma. Ver `consumo.avaliar` — e o
        # dia em que isto foi fundido, o histórico parou de gravar inteiro.
        return avaliar_consumo(
            playbackState="playing" if atual.playing else "paused",
            audible=sessao.audible if sessao is not None else None,
            muted=mudo,
            audible_do_processo=self._audivel_agora(atual),
        )

    def _audivel_agora(self, atual) -> bool | None:
        """Está saindo som do processo que toca? Com folga entre as perguntas.

        A Core Audio custa caro: inicializar COM e enumerar todas as sessões de
        áudio, uma vez por segundo, para responder algo que não muda a cada
        segundo. A resposta vale por alguns segundos, e o intervalo do laço é
        de um — então a sonda é limitada e a última resposta é reaproveitada.

        `None` é "não deu para medir", e ele se propaga: quem não sabe não nega.
        """
        agora = time.monotonic()
        if (
            self._audivel_em is not None
            and (agora - self._audivel_em) < SEGUNDOS_ENTRE_SONDAS_DE_AUDIO
        ):
            return self._audivel

        janela = self.window_focuser.media_window(atual.platform)
        # Sem janela não há processo para perguntar. Não medir não é negar.
        self._audivel = (
            processo_esta_tocando(janela.process) if janela is not None else None
        )
        self._audivel_em = agora
        return self._audivel

    def _poster_para(self, atual, titulo_da_obra: str, e_a_obra: bool) -> str | None:
        """Pôster do catálogo, quando o aplicativo não publica capa.

        O Spotify manda a capa do álbum pela própria API do Windows; o
        navegador não manda nada, então todo filme ficava com o disco cinza.
        O catálogo já sabe achar o título — falta só usar o pôster que ele
        devolve junto.

        A busca acontece fora do laço, num pedido só por título: consultar a
        cada segundo seria uma chamada de rede por segundo para uma imagem que
        não muda.
        """
        if atual.thumbnail_id is not None:
            return None
        if self.catalog is None or not self.catalog.enabled:
            return None

        # O título da OBRA, e não o que a janela leu.
        #
        # Medido com Ben 10 no Max: a janela publica "Enganados Enganados", o
        # nome do episódio, e o catálogo não tem capa para episódio nenhum —
        # então o cartão ficava sem foto. A obra o sistema já conhece, porque a
        # SMTC a nomeou nesta execução, e é dela que a capa vem.
        titulo = titulo_da_obra.strip()
        if not titulo:
            return None
        # "Netflix" não é uma obra. É a página de catálogo — ou, o que dá no
        # mesmo aqui, a SMTC pendurada e a janela dizendo só o nome do serviço.
        # Perguntar ao catálogo por esse nome devolve um título qualquer: o
        # histórico chegou a guardar a capa que o TMDB deu para a busca
        # "Netflix". Sem capa é honesto; com a capa de outro filme, não.
        if _titulo_generico(titulo, atual.app, atual.platform):
            return None
        # Nem de um título que a API de mídia não confirmou. Numa série, o que
        # a janela mostra é o episódio, e pedir a capa dele ao catálogo devolve
        # a capa de outra obra com muita confiança: "Campo dos Sonhos", episódio
        # de Rick and Morty, recebeu o pôster do filme de 1989. Sem capa é
        # honesto — e o logo do serviço, que o cartão já usa nesse caso, diz o
        # que dá para dizer.
        # Sem obra identificada não se pergunta nada. Pedir a capa do episódio
        # devolve a capa de outra obra com muita confiança: "Campo dos Sonhos",
        # episódio de Rick and Morty, recebeu o pôster do filme de 1989.
        if not e_a_obra:
            return None
        # O YouTube não é catálogo de filme, e o Spotify toca música: procurar
        # esses títulos no TMDB devolve a capa de outra coisa. Medido no cartão
        # que chega ao celular — o vídeo "CHEGUEI NA SÍRIA, PAÍS DE CONFLITO E
        # RELIGIÃO" recebeu o pôster de um filme qualquer.
        #
        # Plataforma desconhecida ainda tenta: é o caso de quem foi identificado
        # só pela SMTC, onde o título costuma ser de obra mesmo.
        if atual.platform is not None and atual.platform not in PLATAFORMAS_COM_CATALOGO:
            return None
        chave = (titulo, atual.platform)
        if chave in self._posters:
            return self._posters[chave]

        if chave not in self._posters_em_busca:
            self._posters_em_busca.add(chave)
            # A referência é GUARDADA: o laço de eventos só mantém referência
            # fraca a tarefas, e uma tarefa coletada no meio some sem terminar.
            # Sintoma seria um pôster que às vezes não chega e nunca explica.
            tarefa = asyncio.create_task(self._buscar_poster(titulo, atual.platform))
            self._buscas_de_poster.add(tarefa)
            tarefa.add_done_callback(self._buscas_de_poster.discard)
        return None

    async def _buscar_poster(self, titulo: str, plataforma: Platform | None) -> None:
        chave = (titulo, plataforma)
        try:
            opcoes = await self.catalog.lookup_options(titulo)
            escolhida = self._opcao_da_plataforma(opcoes, plataforma)
            # Guarda inclusive o "não achei": sem isso, um título que o catálogo
            # não conhece seria consultado de novo a cada leitura.
            self._posters[chave] = escolhida.poster_url if escolhida else None
        except Exception:  # noqa: BLE001 - pôster é enfeite, nunca motivo de erro
            self._posters[chave] = None
        finally:
            self._posters_em_busca.discard(chave)

    @staticmethod
    def _opcao_da_plataforma(opcoes: list, plataforma: Platform | None):
        """Entre filme e série de mesmo nome, a que está no serviço aberto.

        "O Justiceiro" é filme de 2004 no Max e série da Marvel no Disney+.
        Assistindo no Disney+, a capa certa é a da série — e essa informação
        está bem ali, na janela que já sabemos qual é.
        """
        if not opcoes:
            return None
        if plataforma is not None:
            for opcao in opcoes:
                if plataforma in opcao.platforms:
                    return opcao
        return opcoes[0]

    async def _broadcast(self, payload: dict) -> None:
        for websocket in list(self._authenticated):
            try:
                await websocket.send_json(payload)
            except Exception:  # noqa: BLE001 - conexão caindo não é erro aqui
                continue

    async def connect(self, websocket: WebSocket) -> bool:
        """Aceita a conexão. Retorna False quando ela foi recusada."""
        if not is_origin_allowed(websocket.headers.get("origin")):
            await websocket.close(code=WS_POLICY_VIOLATION)
            return False

        if len(self._connections) >= self.MAX_CONNECTIONS:
            await websocket.close(code=WS_TRY_AGAIN_LATER)
            return False

        self.pairing_service.initialize()
        await websocket.accept()
        self._connections.add(websocket)
        await self._send_state(websocket, "AUTH_REQUIRED", "Autenticação necessária.")
        return True

    async def reject_non_text_frame(self, websocket: WebSocket) -> None:
        await self._send_error(websocket, "unknown", "INVALID_PAYLOAD", "Frame não suportado.")

    async def disconnect(self, websocket: WebSocket) -> None:
        self._release_input(websocket)
        # Só o que ficou preso de verdade, e não a lista inteira de teclas.
        # O celular desconecta o tempo todo — tela apagada, troca de app,
        # oscilação de rede —, e cada desconexão mandava um Escape para a
        # janela em foco, tirando o filme da tela cheia sozinho.
        self.keyboard_adapter.release_stuck()
        self.pointer_rate_limiter.clear(websocket)
        self.message_rate_limiter.clear(websocket)
        self.navigation_rate_limiter.clear(websocket)
        for action in NAVIGATION_ACTIONS:
            self.navigation_repeat_guard.clear((websocket, action))
        self._authenticated.pop(websocket, None)
        self._connections.discard(websocket)

    async def _send_state(self, websocket: WebSocket, state: str, message: str) -> None:
        response = StateUpdateMessage(state=state, message=message)
        await websocket.send_json(response.model_dump())

    async def _send_error(
        self,
        websocket: WebSocket,
        request_id: str,
        code: ErrorCode,
        message: str,
    ) -> None:
        response = ErrorMessage(requestId=request_id, code=code, message=message)
        await websocket.send_json(response.model_dump())

    async def dispatch(self, websocket: WebSocket, raw: str) -> None:
        # Antes de qualquer processamento: limita inundação por conexão,
        # inclusive de mensagens ainda não autenticadas.
        if not self.message_rate_limiter.allow(websocket):
            await self._send_error(
                websocket,
                "unknown",
                "RATE_LIMITED",
                "Mensagens demais. Tente novamente.",
            )
            return

        try:
            raw_size = len(raw.encode("utf-8"))
        except UnicodeEncodeError:
            await self._send_error(websocket, "unknown", "INVALID_PAYLOAD", "Payload inválido.")
            return

        if raw_size > 8192:
            await self._send_error(websocket, "unknown", "INVALID_PAYLOAD", "Mensagem muito grande.")
            return

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            await self._send_error(websocket, "unknown", "INVALID_JSON", "JSON malformado.")
            return

        if not isinstance(payload, dict):
            await self._send_error(websocket, "unknown", "INVALID_PAYLOAD", "Payload inválido.")
            return

        raw_request_id = payload.get("requestId")
        request_id = raw_request_id if isinstance(raw_request_id, str) and raw_request_id else "unknown"

        protocol_version = payload.get("protocolVersion")
        if type(protocol_version) is not int or protocol_version != 1:
            await self._send_error(
                websocket,
                request_id,
                "PROTOCOL_VERSION_MISMATCH",
                "Versão de protocolo incompatível.",
            )
            return

        message_type = payload.get("type")
        if not isinstance(message_type, str):
            await self._send_error(websocket, request_id, "INVALID_PAYLOAD", "Campo type inválido.")
            return
        if message_type not in KNOWN_CLIENT_TYPES:
            await self._send_error(
                websocket,
                request_id,
                "UNSUPPORTED_MESSAGE",
                "Tipo de mensagem não suportado.",
            )
            return

        try:
            message = self._client_adapter.validate_python(payload)
        except ValidationError:
            await self._send_error(websocket, request_id, "INVALID_PAYLOAD", "Payload inválido.")
            return

        if isinstance(message, PairDeviceMessage):
            await self._pair(websocket, message)
            return
        if isinstance(message, AuthMessage):
            await self._authenticate(websocket, message)
            return
        if websocket not in self._authenticated:
            await self._send_error(websocket, message.requestId, "UNAUTHORIZED", "Autenticação necessária.")
            return

        if isinstance(message, PlatformSelectedMessage):
            await self._handle_open_platform(
                websocket,
                message.requestId,
                message.payload.platform,
                na_busca=message.payload.openSearch,
            )
            return

        if isinstance(message, TextCommandMessage):
            await self._handle_text_command(websocket, message)
            return

        if isinstance(message, SearchMediaMessage):
            await self._handle_search_media(
                websocket,
                message.requestId,
                SearchMediaIntent(
                    type="SEARCH_MEDIA",
                    platform=message.payload.platform,
                    query=message.payload.query,
                ),
            )
            return

        if isinstance(message, MediaControlMessage):
            await self._handle_media_control(websocket, message)
            return

        if isinstance(
            message,
            (VolumeGetMessage, VolumeSetMessage, VolumeDeltaMessage, VolumeMuteToggleMessage),
        ):
            await self._handle_volume_control(websocket, message)
            return

        if isinstance(
            message,
            (
                PointerMoveMessage,
                PointerClickMessage,
                PointerDoubleClickMessage,
                PointerRightClickMessage,
                PointerScrollMessage,
                PointerDownMessage,
                PointerUpMessage,
            ),
        ):
            await self._handle_pointer_control(websocket, message)
            return

        if isinstance(message, (KeyboardTextMessage, KeyboardKeyMessage)):
            await self._handle_keyboard_control(websocket, message)
            return

        if isinstance(message, NavigationMessage):
            await self._handle_navigation(websocket, message)
            return

        if isinstance(message, (ScreenTapMessage, ProfileSelectMessage)):
            await self._handle_screen_control(websocket, message)
            return

        await self._send_error(
            websocket,
            message.requestId,
            "NOT_IMPLEMENTED",
            "Comando conhecido, mas ainda não implementado.",
        )

    async def _handle_text_command(
        self,
        websocket: WebSocket,
        message: TextCommandMessage,
    ) -> None:
        await self._send_state(websocket, "BUSY", "Processando comando...")
        intent = parse_command(message.payload.query)

        if isinstance(intent, UnknownIntent) and self.intent_service is not None:
            device_id = self._authenticated[websocket]
            resolved = await self.intent_service.resolve_unknown(
                device_id,
                message.payload.query,
            )
            if resolved is not None:
                intent = resolved

        if not isinstance(intent, UnknownIntent) and self.intent_service is not None:
            self.intent_service.record(self._authenticated[websocket], intent)

        if isinstance(intent, OpenPlatformIntent):
            await self._handle_open_platform(
                websocket,
                message.requestId,
                intent.platform,
            )
        elif isinstance(intent, SearchMediaIntent):
            await self._handle_search_media(
                websocket,
                message.requestId,
                intent,
            )
        elif isinstance(intent, OpenMediaLinkIntent):
            await self._handle_media_link(websocket, message.requestId, intent)
        elif isinstance(intent, NeedsPlatformIntent):
            await self._ask_where_to_search(websocket, message.requestId, intent)
        elif isinstance(intent, ShowHelpIntent):
            response = CommandResultMessage(
                requestId=message.requestId,
                message="Estes são os comandos disponíveis.",
                data=HelpCommandData(commands=HELP_COMMANDS),
            )
            await websocket.send_json(response.model_dump())
        elif isinstance(intent, MediaControlIntent):
            await self._handle_media_control(
                websocket,
                MediaControlMessage(
                    protocolVersion=1,
                    type=intent.action,
                    requestId=message.requestId,
                ),
            )
        elif isinstance(intent, VolumeControlIntent):
            if intent.action == "SYSTEM_VOLUME_SET" and intent.level is not None:
                volume_message = VolumeSetMessage(
                    protocolVersion=1,
                    type="SYSTEM_VOLUME_SET",
                    requestId=message.requestId,
                    payload={"level": intent.level},
                )
            elif intent.action == "SYSTEM_VOLUME_DELTA" and intent.delta is not None:
                volume_message = VolumeDeltaMessage(
                    protocolVersion=1,
                    type="SYSTEM_VOLUME_DELTA",
                    requestId=message.requestId,
                    payload={"delta": intent.delta},
                )
            elif intent.action == "SYSTEM_MUTE_TOGGLE":
                volume_message = VolumeMuteToggleMessage(
                    protocolVersion=1,
                    type="SYSTEM_MUTE_TOGGLE",
                    requestId=message.requestId,
                )
            else:
                await self._send_error(
                    websocket,
                    message.requestId,
                    "UNKNOWN_COMMAND",
                    "Não entendi esse comando.",
                )
                return
            await self._handle_volume_control(websocket, volume_message)
        else:
            await self._send_error(
                websocket,
                message.requestId,
                "UNKNOWN_COMMAND",
                "Não entendi esse comando.",
            )

        await self._send_state(websocket, "READY", "Computador pronto.")

    async def _handle_reset_input_state(
        self,
        websocket: WebSocket,
        request_id: str,
    ) -> None:
        self._release_input(websocket)
        if not self.keyboard_adapter.release_all():
            await self._send_error(
                websocket,
                request_id,
                "NAVIGATION_FAILED",
                "Não foi possível liberar o teclado.",
            )
            return

        response = CommandResultMessage(
            requestId=request_id,
            message="Teclado e mouse liberados.",
            data=NavigationCommandData(action="RESET_INPUT_STATE"),
        )
        await websocket.send_json(response.model_dump())

    def _release_input(self, websocket: WebSocket) -> None:
        """Solta o que possa ter ficado preso nesta conexão."""
        if websocket in self._held_pointer_buttons:
            self.pointer_adapter.pointer_up()
            self._held_pointer_buttons.discard(websocket)

    async def _handle_media_link(
        self,
        websocket: WebSocket,
        request_id: str,
        intent: OpenMediaLinkIntent,
    ) -> None:
        # A URL já foi validada e reconstruída pelo parser de links; aqui ela
        # ainda passa pela allowlist do launcher, que é quem de fato abre.
        launch = self.platform_launcher.open_url(intent.url)
        if not launch.executed or launch.strategy is None:
            error_message = (
                "Google Chrome não foi encontrado no computador."
                if launch.error == "CHROME_NOT_FOUND"
                else "Não foi possível abrir o link."
            )
            await self._send_error(
                websocket,
                request_id,
                "MEDIA_LINK_FAILED",
                error_message,
            )
            return

        response = CommandResultMessage(
            requestId=request_id,
            message="Link aberto no YouTube.",
            data=MediaLinkCommandData(
                platform=intent.platform,
                strategy=launch.strategy,
            ),
        )
        await websocket.send_json(response.model_dump())

    async def _ask_where_to_search(
        self,
        websocket: WebSocket,
        request_id: str,
        intent: NeedsPlatformIntent,
    ) -> None:
        # Música não passa pelo catálogo de filmes e séries.
        opcoes = [] if intent.music_hint else await self._availability_options(intent.query)
        # Os dois primeiros continuam nos campos antigos: cliente que não
        # conhece a lista segue funcionando como antes.
        availability = opcoes[0] if opcoes else None
        alternativa = opcoes[1] if len(opcoes) > 1 else None

        response = NeedsPlatformMessage(
            requestId=request_id,
            query=intent.query,
            suggestedPlatforms=suggested_search_platforms(intent.music_hint),
            # Música não se procura no Max nem no Disney+: oferecer abrir os
            # dois só polui a escolha quando o pedido foi "toca alguma coisa".
            openOnlyPlatforms=[] if intent.music_hint else open_only_platforms(),
            availability=availability,
            availabilityAlternative=alternativa,
            availabilityOptions=opcoes,
        )
        await websocket.send_json(response.model_dump())

    async def _availability_options(self, query: str) -> list[TitleAvailabilityData]:
        """O que o catálogo achou, com a alternativa quando existe.

        Qualquer falha vira lista vazia e a escolha manual continua igual: o
        catálogo é um atalho, e um atalho indisponível não pode virar um erro na
        cara do usuário.
        """
        if self.catalog is None or not self.catalog.enabled:
            return []
        try:
            # A busca da TELA, e não o resolver: a pergunta aqui é "o que você
            # quis dizer?", que tem uma lista por resposta. Ver
            # `TmdbCatalog.buscar_para_escolha`.
            achados = await self.catalog.buscar_para_escolha(query)
        except Exception:  # noqa: BLE001 - rede, formato, o que for
            return []
        return [
            TitleAvailabilityData(
                title=a.title,
                year=a.year,
                posterUrl=a.poster_url,
                platforms=a.platforms,
                kind=a.kind,
            )
            for a in achados
        ]

    async def _handle_open_platform(
        self,
        websocket: WebSocket,
        request_id: str,
        platform: Platform,
        na_busca: bool = False,
    ) -> None:
        label = PLATFORM_LABELS[platform]
        launch = self.platform_launcher.open(platform, na_busca=na_busca)
        if not launch.executed or launch.strategy is None:
            error_message = (
                "Google Chrome não foi encontrado no computador."
                if launch.error == "CHROME_NOT_FOUND"
                else f"Não foi possível abrir o {label}."
            )
            await self._send_error(
                websocket,
                request_id,
                "PLATFORM_OPEN_FAILED",
                error_message,
            )
            return

        response = CommandResultMessage(
            requestId=request_id,
            message=f"{label} aberto.",
            data=PlatformCommandData(
                platform=platform,
                executed=True,
                strategy=launch.strategy,
            ),
        )
        await websocket.send_json(response.model_dump())

    async def _handle_search_media(
        self,
        websocket: WebSocket,
        request_id: str,
        intent: SearchMediaIntent,
    ) -> None:
        label = PLATFORM_LABELS[intent.platform]
        launch = self.media_search_launcher.search(intent.platform, intent.query)
        if not launch.executed or launch.strategy is None:
            await self._send_error(
                websocket,
                request_id,
                "MEDIA_SEARCH_FAILED",
                f"Não foi possível abrir a pesquisa no {label}.",
            )
            return

        response = CommandResultMessage(
            requestId=request_id,
            message=f"Pesquisa aberta no {label}.",
            data=SearchMediaCommandData(
                platform=intent.platform,
                strategy=launch.strategy,
            ),
        )
        await websocket.send_json(response.model_dump())

    async def _handle_media_control(
        self,
        websocket: WebSocket,
        message: MediaControlMessage,
    ) -> None:
        session = self.media_session_detector.detect()
        if session is None:
            await self._send_error(
                websocket,
                message.requestId,
                "MEDIA_SESSION_NOT_FOUND",
                # Não é falha do controle: é o estado mais comum de todos,
                # alguém que pegou o celular antes de começar a assistir. A
                # mensagem diz o que fazer em vez de só constatar a ausência.
                "Nada tocando agora. Abra uma plataforma para começar.",
            )
            return

        label = PLATFORM_LABELS[session.platform]

        # Sem isto a tecla ia para a janela que estivesse na frente: "tela
        # cheia" digitava um "f" no editor de código, "+10s" mandava seta para
        # o Explorer, e a resposta dizia "comando enviado" do mesmo jeito.
        # Falhar em focar não impede o envio — o alvo pode já estar na frente —,
        # mas o resultado diz em qual janela a tecla caiu.
        focused = self.window_focuser.focus_platform(session.platform)

        if not self.media_adapter.supports(message.type, session.platform):
            await self._send_error(
                websocket,
                message.requestId,
                "MEDIA_ACTION_UNSUPPORTED",
                f"{MEDIA_ACTION_LABELS[message.type]} não é suportado no {label}.",
            )
            return

        if message.type == "MEDIA_FULLSCREEN" and session.platform != "SPOTIFY":
            executed = self._enter_fullscreen(session.platform)
        elif (pela_ponte := await self._comandar_pela_ponte(
                message.type, session.platform)) is not None:
            # Fase 16 — o comando foi direto ao `<video>` da aba que o árbitro
            # escolheu. Sem roubar foco, sem depender de qual aba está ativa, e
            # com play e pause SEPARADOS em vez de um toggle cego.
            executed = pela_ponte
        elif message.type == "MEDIA_PLAY_PAUSE":
            executed = self._toggle_play_pause(session.platform)
        else:
            executed = self.media_adapter.execute(message.type, session.platform)
        if not executed:
            await self._send_error(
                websocket,
                message.requestId,
                "MEDIA_CONTROL_FAILED",
                "Controle de mídia indisponível.",
            )
            return

        response = CommandResultMessage(
            requestId=message.requestId,
            message=(
                f"Comando enviado ao {label}."
                if focused
                else f"Comando enviado ao {label} — deixe a janela dele visível."
            ),
            data=MediaCommandData(
                action=message.type,
                platform=session.platform,
                session=session.kind,
                focused=focused,
            ),
        )
        await websocket.send_json(response.model_dump())

    def _clicar_no_video(self, platform: Platform, duplo: bool) -> bool | None:
        """Clique no meio do vídeo. None quando não há janela para clicar.

        É o mesmo caminho que resolveu a tela cheia: o atalho de teclado é de
        cada site e nenhum deles o aplica igual, enquanto clicar no vídeo é o
        gesto que todo player web implementa — um clique alterna play/pause,
        dois alternam tela cheia.
        """
        # A extensão sabe ONDE o vídeo está; a janela não.
        #
        # Mirar o centro da janela só acerta enquanto o vídeo ocupa o meio da
        # tela — e isso é falso em dois casos medidos. No Prime, o vídeo toca
        # em `/detail/`, com a lista de episódios e a sinopse em volta. Na
        # Netflix pausada no plano com anúncios, o meio da janela é do anúncio,
        # e o clique ainda por cima mirava um link de anunciante.
        #
        # Quando a ponte diz onde ele está, usa-se isso. Quando não diz, o
        # centro da janela continua sendo o melhor palpite disponível.
        alvo = self._centro_do_video(platform)
        if alvo is not None and self._clicar_na_janela(platform, *alvo, duplo):
            return True

        window = self.window_focuser.find(platform)
        if window is None:
            return None
        centro = self.window_focuser.center_of(window)
        if centro is None:
            return None

        self.window_focuser.focus(window)
        if not self.pointer_adapter.move_to(*centro):
            return None
        return self.pointer_adapter.double_click() if duplo else self.pointer_adapter.click()

    def _centro_do_video(self, platform: Platform) -> tuple[float, float] | None:
        """Onde o vídeo está na janela, em fração. `None` sem extensão.

        Vem da própria página (`ondeEstaOVideo` em `index.js`), e em FRAÇÃO
        para sobreviver ao escalonamento do Windows: 150% de zoom muda os
        pixels e não muda a proporção.
        """
        sessao = self.bridge_state.atual_de(platform)
        if sessao is None:
            return None
        if sessao.videoCentroX is None or sessao.videoCentroY is None:
            return None
        return (sessao.videoCentroX, sessao.videoCentroY)

    async def _handle_screen_control(
        self,
        websocket: WebSocket,
        message: ScreenTapMessage | ProfileSelectMessage,
    ) -> None:
        """Um toque na foto da tela vira um clique dentro da janela.

        O caminho é o mesmo do play/pause por clique, que já provou funcionar
        nos seis serviços: achar a janela, trazer para frente, mirar, clicar. A
        única novidade é de onde vem a mira — do dedo na imagem, em vez do
        centro do vídeo.
        """
        platform = message.payload.platform
        if isinstance(message, ScreenTapMessage):
            x, y, duplo = message.payload.x, message.payload.y, message.payload.double
        else:
            perfil = self.profile_store.buscar(platform, message.payload.profileId)
            if perfil is None:
                await self._send_error(
                    websocket,
                    message.requestId,
                    "PROFILE_NOT_FOUND",
                    "Esse perfil não está mais cadastrado.",
                )
                return
            x, y, duplo = perfil.x, perfil.y, False

        if not self._clicar_na_janela(platform, x, y, duplo):
            await self._send_error(
                websocket,
                message.requestId,
                "SCREEN_CONTROL_FAILED",
                f"{PLATFORM_LABELS[platform]} não está aberto no computador.",
            )
            return

        await websocket.send_json(CommandResultMessage(
            requestId=message.requestId,
            message="Toque enviado." if isinstance(message, ScreenTapMessage)
            else f"Entrando como {perfil.nome}.",
            data=ScreenCommandData(
                action=message.type,
                platform=platform,
                executed=True,
            ),
        ).model_dump())

    def _clicar_na_janela(self, platform: Platform, x: float, y: float, duplo: bool) -> bool:
        """Clique numa posição relativa da janela da plataforma.

        Relativa, e não absoluta: a janela pode ter mudado de tamanho — ou de
        monitor, o que aconteceu no meio da medição — desde a foto que a pessoa
        está vendo. A fração continua valendo; o pixel não continuaria.
        """
        janela = self.window_focuser.find(platform)
        if janela is None:
            return False
        rect = self.window_capture.retangulo(janela)
        if rect is None:
            return False

        alvo = ponto_na_tela(rect, x, y)
        # Enquanto o clique errado não for explicado, o caminho inteiro fica
        # visível no terminal: fração recebida, retângulo no instante do clique
        # e pixel final. É o suficiente para separar "a foto estava velha" de
        # "a conta está errada" sem ter de adivinhar de novo.
        print(
            f"[toque] {platform} fracao=({x:.4f}, {y:.4f}) "
            f"janela={rect.esquerda},{rect.topo} {rect.largura}x{rect.altura} "
            f"-> pixel={alvo} | {janela.title[:40]!r}",
            flush=True,
        )

        self.window_focuser.focus(janela)
        if not self.pointer_adapter.move_to(*alvo):
            return False
        return self.pointer_adapter.double_click() if duplo else self.pointer_adapter.click()

    #: Quanto os botões de avançar e retroceder pulam. O mesmo dos rótulos em
    #: `MEDIA_ACTION_LABELS`, e o mesmo que as teclas de mídia já faziam.
    SEGUNDOS_DE_SALTO = 10.0

    async def _comandar_pela_ponte(self, tipo: str, platform: Platform) -> bool | None:
        """Comanda o `<video>` pela extensão. `None` quando por ali não deu.

        ## Por que isto vem ANTES da tecla

        O caminho antigo é uma tecla: `_toggle_play_pause` foca a janela do
        Chrome e aperta a barra de espaço. Ele funciona, e continua sendo o
        plano B. Mas tem três limites, e dois deles estão medidos:

            rouba o foco       focar a janela tira o foco de onde a pessoa
                               estava. É visível e é irritante.

            erra de aba        a barra de espaço vai para a aba ATIVA. Medido
                               na Fase 14: em 6 dos 18 instantes com duas abas
                               tocando havia MAIS DE UMA aba ativa — janelas
                               diferentes, cada uma com a sua. A tecla não tem
                               como escolher; o comando tem, e escolhe a que o
                               árbitro apontou.

            toggle cego        `MEDIA_PLAY_PAUSE` alterna o que estiver lá. Se o
                               estado real e o suposto divergirem, o botão faz o
                               contrário do desenhado — foi a queixa "pausa e
                               não volta a play". Aqui play e pause são
                               comandos DIFERENTES, decididos pelo estado que a
                               própria página acabou de reportar.

        ## E por que ele pode desistir

        `None` significa "por aqui não deu": sem extensão, sem aba conhecida,
        Chrome fechado, ou a página não respondeu em um segundo e meio. Quem
        chama cai para a tecla. Um caminho novo que quebrasse o antigo seria
        pior do que não existir — quem não instalou a extensão continua com o
        controle que sempre teve.
        """
        sessao = self.bridge_state.atual_de(platform)
        if sessao is None or sessao.tabId is None:
            return None

        if tipo == "MEDIA_PLAY_PAUSE":
            acao, valor = ("PAUSE" if sessao.tocando else "PLAY"), None
        elif tipo == "MEDIA_SEEK_BACK":
            acao, valor = "SEEK_BY", -self.SEGUNDOS_DE_SALTO
        elif tipo == "MEDIA_SEEK_FORWARD":
            acao, valor = "SEEK_BY", self.SEGUNDOS_DE_SALTO
        else:
            # Volume, próxima faixa, tela cheia: não são do elemento, ou não
            # foram medidos. Uma ação sem executor do outro lado é uma promessa
            # que falha em silêncio.
            return None

        comando = fila_de_comandos.enfileirar(
            acao, tabId=sessao.tabId, sessionId=sessao.sessionId, valor=valor,
        )
        if comando is None:
            return None
        resultado = await fila_de_comandos.esperar(comando)
        # Resposta negativa também cai para a tecla: "sem elemento" ou "outra
        # reprodução" são motivos para tentar de outro jeito, não para desistir.
        if resultado is None or not resultado.ok:
            return None
        return True

    def _toggle_play_pause(self, platform: Platform) -> bool:
        """Play/pause pela barra de espaço, com a janela em foco.

        Nem a tecla global de mídia nem o clique no meio do vídeo.

        A tecla `VK_MEDIA_PLAY_PAUSE` depende do subsistema de mídia do Windows
        rotear o evento até o aplicativo certo — o mesmo subsistema cuja API
        ficou pendurada nesta máquina por minutos. Quando ele adoece, a tecla
        vai para lugar nenhum e o botão "não pega", sem erro nenhum aparecer.

        O clique no centro funciona enquanto o vídeo ocupa o meio da tela — que
        é exatamente o que deixa de valer quando ele pausa. Medido na tela do
        usuário: no plano com anúncios, pausar a Netflix cobre a direita com um
        anúncio e encolhe o player num cartão à esquerda. O centro da janela
        cai no anúncio, então o botão pausava e não despausava — e ainda mirava
        um link de anunciante, que é pior do que não fazer nada.

        A barra de espaço é o atalho que todo player web implementa e não
        depende de onde o vídeo está na tela. O foco na janela é o que faz a
        tecla chegar no lugar certo sem passar pelo subsistema de mídia.

        O Spotify segue fora: é aplicativo, não página, e a tecla de mídia
        funciona nele.
        """
        if platform == "SPOTIFY":
            return self.media_adapter.execute("MEDIA_PLAY_PAUSE", platform)
        janela = self.window_focuser.find(platform)
        if janela is None:
            # Sem janela para focar, a tecla é a única tentativa que resta.
            return self.media_adapter.execute("MEDIA_PLAY_PAUSE", platform)
        self.window_focuser.focus(janela)
        return self.keyboard_adapter.press_key("SPACE")

    def _enter_fullscreen(self, platform: Platform) -> bool:
        """Duplo clique no meio do vídeo, em vez da tecla F.

        O atalho de teclado é de cada site e nenhum deles o aplica igual: no
        Max, com a janela em foco, o F não fazia absolutamente nada — medido.
        Já o duplo clique sobre o vídeo é o gesto de tela cheia que todo player
        web implementa, e foi o que funcionou no uso real.

        A saída continua sendo Escape, que é padrão do navegador e não depende
        do site.

        Vale o mesmo aviso do play/pause: mirar o centro só acerta o vídeo
        enquanto ele ocupa o meio da tela. Com a reprodução pausada no plano com
        anúncios, o meio é do anúncio — então o caso a reproduzir é sempre com
        o vídeo tocando.
        """
        clicou = self._clicar_no_video(platform, duplo=True)
        if clicou is None:
            return self.media_adapter.execute("MEDIA_FULLSCREEN", platform)
        return clicou

    async def _handle_volume_control(
        self,
        websocket: WebSocket,
        message: VolumeGetMessage
        | VolumeSetMessage
        | VolumeDeltaMessage
        | VolumeMuteToggleMessage,
    ) -> None:
        # LOCAL primeiro: mexer só no aplicativo que está tocando. Se não der,
        # cai para o volume do Windows — e o fallback vai explícito na resposta,
        # nunca escondido.
        local = await self._try_local_volume(message)
        if local is not None:
            await self._send_volume_result(websocket, message, *local)
            return

        try:
            if isinstance(message, VolumeGetMessage):
                state = await self.volume_adapter.get_state()
            elif isinstance(message, VolumeSetMessage):
                state = await self.volume_adapter.set_level(message.payload.level)
            elif isinstance(message, VolumeDeltaMessage):
                state = await self.volume_adapter.change_level(message.payload.delta)
            else:
                state = await self.volume_adapter.toggle_mute()
        except WindowsVolumeError:
            await self._send_error(
                websocket,
                message.requestId,
                "SYSTEM_VOLUME_FAILED",
                "Controle de volume indisponível.",
            )
            return

        await self._send_volume_result(websocket, message, state, "GLOBAL", None)

    async def _try_local_volume(self, message):
        """Tenta o volume do aplicativo ativo. None quando não é possível."""
        if self.app_volume_adapter is None:
            return None
        session = self.media_session_detector.detect()
        if session is None:
            return None

        try:
            if isinstance(message, VolumeGetMessage):
                state = self.app_volume_adapter.get_state(session.platform)
            elif isinstance(message, VolumeSetMessage):
                state = self.app_volume_adapter.set_level(
                    session.platform, message.payload.level,
                )
            elif isinstance(message, VolumeDeltaMessage):
                state = self.app_volume_adapter.change_level(
                    session.platform, message.payload.delta,
                )
            else:
                state = self.app_volume_adapter.toggle_mute(session.platform)
        except AppVolumeUnavailable:
            return None
        except Exception:  # noqa: BLE001 - qualquer falha local cai no global
            return None

        return state, "LOCAL", SCOPE_LABELS.get(state.process, state.process)

    async def _send_volume_result(self, websocket, message, state, scope, target) -> None:
        alvo = target or "Windows"
        # "geral" e não "(fallback)": o que a pessoa precisa saber é que o
        # ajuste pegou o computador inteiro, e não só o aplicativo. A palavra
        # em inglês aparecia na tela do celular sem explicar nada.
        prefixo = f"Volume do {alvo}" if scope == "LOCAL" else "Volume geral do Windows"
        response_message = (
            f"{prefixo}: mudo {'ativado' if state.muted else 'desativado'}, {state.level}%."
            if isinstance(message, VolumeMuteToggleMessage)
            else f"{prefixo}: {state.level}%."
        )
        response = CommandResultMessage(
            requestId=message.requestId,
            message=response_message,
            data=VolumeCommandData(
                action=message.type,
                level=state.level,
                muted=state.muted,
                scope=scope,
                target=target,
            ),
        )
        await websocket.send_json(response.model_dump())

    async def _handle_pointer_control(
        self,
        websocket: WebSocket,
        message: PointerMoveMessage
        | PointerClickMessage
        | PointerDoubleClickMessage
        | PointerRightClickMessage
        | PointerScrollMessage
        | PointerDownMessage
        | PointerUpMessage,
    ) -> None:
        if isinstance(message, PointerMoveMessage):
            if not self.pointer_rate_limiter.allow(websocket):
                await self._send_error(
                    websocket,
                    message.requestId,
                    "POINTER_RATE_LIMITED",
                    "Movimento do touchpad limitado.",
                )
                return
            executed = self.pointer_adapter.move(message.payload.dx, message.payload.dy)
        elif isinstance(message, PointerClickMessage):
            executed = self.pointer_adapter.click()
        elif isinstance(message, PointerDoubleClickMessage):
            executed = self.pointer_adapter.double_click()
        elif isinstance(message, PointerRightClickMessage):
            executed = self.pointer_adapter.right_click()
        elif isinstance(message, PointerScrollMessage):
            executed = self.pointer_adapter.scroll(message.payload.delta)
        elif isinstance(message, PointerDownMessage):
            executed = self.pointer_adapter.pointer_down()
        else:
            executed = self.pointer_adapter.pointer_up()

        if not executed:
            await self._send_error(
                websocket,
                message.requestId,
                "POINTER_CONTROL_FAILED",
                "Touchpad indisponível.",
            )
            return

        if isinstance(message, PointerDownMessage):
            self._held_pointer_buttons.add(websocket)
        elif isinstance(message, PointerUpMessage):
            self._held_pointer_buttons.discard(websocket)

        response = CommandResultMessage(
            requestId=message.requestId,
            message="Comando do touchpad executado.",
            data=PointerCommandData(action=message.type),
        )
        await websocket.send_json(response.model_dump())

    async def _handle_keyboard_control(
        self,
        websocket: WebSocket,
        message: KeyboardTextMessage | KeyboardKeyMessage,
    ) -> None:
        # A tecla vai para a janela em primeiro plano, seja ela qual for. Sem
        # trazer a plataforma para frente, "digitar no computador" digitava no
        # editor de código que estivesse aberto — e o controle respondia "texto
        # enviado", porque enviado ele foi. É o mesmo ponto cego que o módulo de
        # foco resolveu para as teclas de mídia, e que ficou de fora aqui.
        janela = self.window_focuser.media_window()
        if janela is not None:
            self.window_focuser.focus(janela)

        if isinstance(message, KeyboardTextMessage):
            executed = self.keyboard_adapter.write_text(message.payload.text)
            response_message = "Texto enviado."
        else:
            executed = self.keyboard_adapter.press_key(message.payload.key)
            response_message = "Tecla enviada."

        if not executed:
            await self._send_error(
                websocket,
                message.requestId,
                "KEYBOARD_CONTROL_FAILED",
                "Teclado remoto indisponível.",
            )
            return

        response = CommandResultMessage(
            requestId=message.requestId,
            message=response_message,
            data=KeyboardCommandData(action=message.type),
        )
        await websocket.send_json(response.model_dump())

    async def _handle_navigation(
        self,
        websocket: WebSocket,
        message: NavigationMessage,
    ) -> None:
        # O reset é a saída de emergência para tecla presa: nunca pode ser
        # barrado por limite nem por guarda de repetição.
        if message.type == "RESET_INPUT_STATE":
            await self._handle_reset_input_state(websocket, message.requestId)
            return

        # Limite próprio, separado do teclado: o direcional repete ao segurar a
        # seta, e uma repetição acelerada não pode consumir a cota do teclado.
        if not self.navigation_rate_limiter.allow(websocket):
            await self._send_error(
                websocket,
                message.requestId,
                "NAVIGATION_RATE_LIMITED",
                "Navegação rápida demais.",
            )
            return

        # Confirmar e voltar não repetem: entrariam em vários itens ou sairiam
        # de várias telas de uma vez.
        if message.type not in REPEATABLE_ACTIONS:
            if not self.navigation_repeat_guard.allow((websocket, message.type)):
                await self._send_error(
                    websocket,
                    message.requestId,
                    "NAVIGATION_RATE_LIMITED",
                    "Aguarde antes de repetir esse comando.",
                )
                return

        if not self.keyboard_adapter.press_key(NAVIGATION_KEYS[message.type]):
            await self._send_error(
                websocket,
                message.requestId,
                "NAVIGATION_FAILED",
                "Navegação indisponível.",
            )
            return

        response = CommandResultMessage(
            requestId=message.requestId,
            message=f"{NAVIGATION_LABELS[message.type]} enviado.",
            data=NavigationCommandData(action=message.type),
        )
        await websocket.send_json(response.model_dump())

    async def _pair(self, websocket: WebSocket, message: PairDeviceMessage) -> None:
        result = self.pairing_service.attempt(
            message.payload.pin,
            message.payload.deviceName,
        )
        if not result.success or not result.device_id or not result.token:
            code: ErrorCode = result.code if result.code in {
                "PIN_INVALID", "PIN_EXPIRED", "TOO_MANY_ATTEMPTS", "INTERNAL_ERROR"
            } else "INTERNAL_ERROR"
            await self._send_error(websocket, message.requestId, code, result.message)
            return

        self._authenticated[websocket] = result.device_id
        response = PairResultMessage(
            requestId=message.requestId,
            message=result.message,
            deviceId=result.device_id,
            token=result.token,
        )
        await websocket.send_json(response.model_dump())
        await self._send_state(websocket, "READY", "Computador pronto.")
        await self._send_now_playing(websocket)

    async def _authenticate(self, websocket: WebSocket, message: AuthMessage) -> None:
        if not self.device_store.authenticate(message.payload.deviceId, message.payload.token):
            await self._send_error(websocket, message.requestId, "INVALID_TOKEN", "Token inválido.")
            return

        self._authenticated[websocket] = message.payload.deviceId
        response = AuthResultMessage(
            requestId=message.requestId,
            message="Autenticação concluída.",
        )
        await websocket.send_json(response.model_dump())
        await self._send_state(websocket, "READY", "Computador pronto.")
        await self._send_now_playing(websocket)

    async def _send_now_playing(self, websocket: WebSocket) -> None:
        """Estado atual assim que a conexão fica pronta.

        Sem isto o cartão só apareceria na próxima mudança — e se o filme
        estivesse tocando parado, o celular ficaria sem nada na tela até alguém
        apertar pausa.
        """
        try:
            payload = self._last_now_playing or await self._read_now_playing()
            self._last_now_playing = payload
            await websocket.send_json(payload)
        except Exception:  # noqa: BLE001 - o cartão nunca derruba a sessão
            return
