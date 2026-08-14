"""O que está tocando no computador, pela SMTC do Windows.

A SMTC é a mesma fonte que alimenta o painel de mídia do próprio Windows: ela
sabe o que toca, se está pausado, em que segundo está e — quando o aplicativo
publica — a capa.

Uma limitação medida, não escondida: o Chrome publica só o nome do site como
título ("Netflix"), nunca o do episódio. O título da janela, por outro lado,
tem o nome do conteúdo. Por isso as duas fontes são combinadas: a SMTC dá
estado e progresso, a janela dá o nome. Sozinha, nenhuma das duas entrega o
cartão completo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
import asyncio
import hashlib
import re
import sys
import time
import unicodedata

from app.schemas.ws import Platform


# Windows.Media.Control.GlobalSystemMediaTransportControlsSessionPlaybackStatus
STATUS_PLAYING = 4
STATUS_PAUSED = 5

# Sufixos que o navegador cola no título da janela e não fazem parte do nome.
_SUFIXOS_NAVEGADOR = (
    " - Google Chrome",
    " — Google Chrome",
    " - Chrome",
    " - Microsoft Edge",
)

# Depois do navegador sai o nome do serviço: o título da aba costuma ser
# "Nome do Episódio - Netflix". O que interessa no cartão é o nome, não o
# serviço, que já aparece em outro lugar da tela.
_SUFIXOS_SERVICO = (
    "netflix", "youtube", "max", "hbo max", "disney+", "disney plus",
    "prime video", "amazon prime video", "spotify",
)

_PLATAFORMA_POR_APP: dict[str, Platform] = {
    "spotify": "SPOTIFY",
}


def _plataforma_do_app(app: str | None) -> Platform | None:
    """O serviço pelo identificador do aplicativo que publica a mídia.

    Por conteúdo e não por igualdade: a SMTC não devolve "Spotify", devolve o
    identificador do pacote. Medido nesta máquina —
    "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify", que é o Spotify instalado
    pela Loja. A comparação exata só reconhecia a versão que se identifica pelo
    nome puro, então tudo que tocava no Spotify daqui ficava sem serviço.
    """
    normalizado = (app or "").strip().lower()
    if not normalizado:
        return None
    for pedaco, plataforma in _PLATAFORMA_POR_APP.items():
        if pedaco in normalizado:
            return plataforma
    return None

# O mesmo nome de serviço que a limpeza descarta identifica a plataforma.
_PLATAFORMA_POR_SERVICO: dict[str, Platform] = {
    "netflix": "NETFLIX",
    "youtube": "YOUTUBE",
    "max": "MAX",
    "hbo max": "MAX",
    "disney+": "DISNEY_PLUS",
    "disney plus": "DISNEY_PLUS",
    "prime video": "PRIME_VIDEO",
    "amazon prime video": "PRIME_VIDEO",
    "spotify": "SPOTIFY",
}


def plataforma_no_titulo(titulo: str | None) -> Platform | None:
    """O serviço nomeado no próprio título, quando ele está lá.

    A plataforma vinha só do aplicativo, e o mapa de aplicativos conhece um só
    — o Spotify. Tudo que toca no navegador, que é quase tudo, ficava sem
    serviço. Medido no histórico real: 3530 dos 3650 segundos gravados não
    contavam para nada, porque só entra na conta o que tem plataforma.

    E a pista sempre esteve à vista, nas duas fontes: a SMTC publica "Prime
    Video: Batman: Caped Crusader" e a janela, "Episódio - Netflix - Google
    Chrome". `limpar_titulo_de_janela` joga esse pedaço fora justamente por não
    ser o nome da obra — mas antes de jogar fora dá para ler quem é.
    """
    if not titulo:
        return None
    limpo = re.sub(r"^\(\d+\)\s*", "", _sem_invisiveis(titulo).strip())
    # A marca de janela travada sai antes do resto: com ela no fim, o sufixo do
    # navegador deixa de ser o fim do texto e o serviço não é reconhecido.
    limpo = _sem_marca_de_travado(limpo).lower()
    for sufixo in _SUFIXOS_NAVEGADOR:
        if limpo.endswith(sufixo.lower()):
            limpo = limpo[: -len(sufixo)].strip()
            break

    # Do nome mais longo para o mais curto: "hbo max" tem de ser testado antes
    # de "max", ou o serviço certo nunca seria alcançado.
    for servico in sorted(_PLATAFORMA_POR_SERVICO, key=len, reverse=True):
        plataforma = _PLATAFORMA_POR_SERVICO[servico]
        # Sozinho é a página de catálogo; com prefixo ou sufixo é o conteúdo.
        if limpo == servico or limpo.startswith(f"{servico}:"):
            return plataforma
        if any(limpo.endswith(f"{sep}{servico}") for sep in _SEPARADORES):
            return plataforma
    return None


@dataclass(frozen=True)
class NowPlaying:
    title: str
    artist: str | None
    app: str | None
    platform: Platform | None
    playing: bool
    position_seconds: float | None
    duration_seconds: float | None
    thumbnail: bytes | None
    # O episódio, quando a obra é uma série. Separado do título de propósito:
    # o que identifica a obra no catálogo e no histórico é a série, e o
    # episódio é o detalhe de onde ela está — cabe no cartão, não na chave.
    episode: str | None = None
    # A leitura veio da SMTC, que sabe o que está tocando, ou só da janela
    # aberta, que sabe o nome da aba? Ver `da_janela`.
    trustworthy: bool = True
    # A posição é desta reprodução, mas parou de ser atualizada. Continua
    # valendo para mostrar; não vale para avançar sozinha. Ver `RelogioDaMidia`.
    position_stale: bool = False

    @property
    def thumbnail_id(self) -> str | None:
        """Identidade da capa, para o celular só rebaixar quando ela muda."""
        if not self.thumbnail:
            return None
        return hashlib.sha256(self.thumbnail).hexdigest()[:16]


# Separadores entre o nome da obra e o do serviço, no título da janela.
#
# O "•" (U+2022) não é o mesmo caractere que o "·" (U+00B7) que já estava aqui,
# e é justamente o que o Max usa. Medido com A Casa do Dragão tocando: a janela
# dizia "⁨The Treasons at Tumbleton⁩ • HBO Max" e nada era reconhecido — nem o
# serviço, nem o fim do nome do episódio.
_SEPARADORES = (" - ", " — ", " | ", " · ", " • ")


def _sem_invisiveis(texto: str) -> str:
    """Sem as marcas de formatação que não se veem na tela.

    O Max envolve o nome do episódio em U+2068/U+2069, o par de isolamento
    direcional. Invisíveis na janela, mas viajam para o histórico e para a
    busca no catálogo — onde título nenhum casa com elas no meio.
    """
    return "".join(c for c in texto if unicodedata.category(c) != "Cf")


# O que o Windows pendura no fim do título de uma janela que parou de responder.
_PARENTESES_NO_FIM = re.compile(r"\s*\([^()]*\)\s*$")


def _sem_marca_de_travado(titulo: str) -> str:
    """Sem o "(Não está respondendo)" que o Windows cola no título.

    Medido com o Chrome pendurado tocando um episódio: a janela dizia
    "⁨46 Long⁩ • HBO Max - Google Chrome (Não está respondendo)". O sufixo do
    navegador deixou de ser o fim do texto, então nada era reconhecido — nem o
    serviço, nem o fim do nome — e a frase inteira, marca de travamento
    incluída, virava o título no cartão do celular.

    Sem lista de idiomas: a marca é traduzida em todo Windows, e enumerá-las
    seria uma corrida perdida. O que identifica o caso é o que fica DEPOIS de
    tirar o parêntese — se aquilo termina em nome de navegador, o parêntese era
    a marca. "Duna (2021)" não termina, e continua inteiro.
    """
    sem_parenteses = _PARENTESES_NO_FIM.sub("", titulo).strip()
    if sem_parenteses == titulo.strip() or not sem_parenteses:
        return titulo
    baixo = sem_parenteses.lower()
    if any(baixo.endswith(sufixo.lower()) for sufixo in _SUFIXOS_NAVEGADOR):
        return sem_parenteses
    return titulo


def limpar_titulo_de_janela(titulo: str) -> str:
    """Tira do título da janela o que é do navegador e do serviço.

    "(2) Nome do Episódio - Netflix - Google Chrome" vira "Nome do Episódio".
    Se sobrar só o nome do serviço, ele é devolvido como está: é o que
    acontece numa página de catálogo, onde não há conteúdo nomeado.
    """
    limpo = _sem_invisiveis(titulo).strip()
    # O Chrome prefixa com a contagem de notificações da aba.
    limpo = re.sub(r"^\(\d+\)\s*", "", limpo).strip()
    limpo = _sem_marca_de_travado(limpo)

    # O Prime Video põe o nome do serviço na frente, não atrás:
    # "Prime Video: Batman: Caped Crusader". Sem tirar isso, a busca do pôster
    # procura por um título que não existe em catálogo nenhum.
    for servico in _SUFIXOS_SERVICO:
        prefixo = f"{servico}:"
        if limpo.lower().startswith(prefixo):
            sobra = limpo[len(prefixo):].strip()
            if sobra:
                limpo = sobra
            break

    for sufixo in _SUFIXOS_NAVEGADOR:
        if limpo.lower().endswith(sufixo.lower()):
            limpo = limpo[: -len(sufixo)].strip()
            break

    for servico in _SUFIXOS_SERVICO:
        for separador in _SEPARADORES:
            fim = f"{separador}{servico}"
            if limpo.lower().endswith(fim):
                sobra = limpo[: -len(fim)].strip()
                # Só corta se sobrar nome: "Netflix" sozinho continua "Netflix".
                if sobra:
                    limpo = sobra
                break

    # O serviço na frente separado por traço, e não por dois-pontos: é como o
    # serviço instalado como aplicativo nomeia a janela.
    #
    # Medido com a Netflix instalada: a janela diz "Netflix - Home - Netflix".
    # O corte do sufixo tira o último pedaço e sobra "Netflix - Home" — que não
    # é o nome de nenhuma página conhecida, então passava por obra. Custou caro:
    # essa janela ganhava da janela do Prime Video na hora de escolher qual
    # estava tocando, e o cartão anunciava "Netflix - Home" enquanto o usuário
    # assistia Batman no Prime Video, com o logo errado junto.
    for servico in _SUFIXOS_SERVICO:
        for separador in _SEPARADORES:
            comeco = f"{servico}{separador}"
            if limpo.lower().startswith(comeco):
                sobra = limpo[len(comeco):].strip()
                if sobra:
                    limpo = sobra
                break

    # "- Season 1" e "- Temporada 2" dizem menos que o nome da série, e
    # atrapalham a busca no catálogo.
    limpo = re.sub(
        r"\s*[-–—]\s*(season|temporada)\s*\d+\s*$", "", limpo, flags=re.IGNORECASE,
    ).strip()
    return limpo.strip(" -–—|·") or titulo.strip()


# Páginas do próprio serviço, não obras. O título da janela é o nome da PÁGINA
# aberta, e navegar pelo catálogo é o que a pessoa mais faz antes de escolher.
#
# Medido com a Netflix logada: a janela diz "Home - Netflix", a limpeza tira o
# serviço e sobra "Home" — que não é o nome do serviço, então escapava do filtro
# e entrava no histórico como um filme assistido. As outras seções do menu
# (Shows, Movies, Games, My List) fariam o mesmo, uma linha para cada. E, no
# Prime Video sem login, sobra a frase de marketing inteira.
#
# Lista explícita porque não há regra que separe o nome de uma seção do nome de
# uma obra: "Games" poderia ser um filme. O que faltar aqui custa uma linha a
# mais no histórico, e é corrigido acrescentando o caso quando ele aparecer.
_PAGINAS_INICIAIS = {
    # Prime Video sem login.
    "watch movies, tv shows, sports, and live tv",
    # Seções do menu, em inglês e português.
    "home",
    "inicio",
    "shows",
    "series",
    "movies",
    "filmes",
    "games",
    "jogos",
    "my list",
    "minha lista",
    "new & popular",
    "novidades",
    "browse by languages",
    "navegar por idiomas",
}


# Um endereço nunca é o nome de uma obra. O Chrome mostra a URL como título
# enquanto a página não define a sua — e quando ninguém está logado ela nunca
# define. Medido com o Max aberto: "play.hbomax.com" entraria no histórico como
# um filme assistido, e ainda iria procurar capa no catálogo.
_PARECE_ENDERECO = re.compile(r"^[a-z0-9.-]+\.[a-z]{2,6}(/\S*)?$")


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def _titulo_generico(titulo: str, app: str | None, platform: Platform | None) -> bool:
    """O título não diz o que está tocando: é o nome do serviço ou a home dele."""
    normalizado = titulo.strip().lower()
    if not normalizado:
        return True
    if _sem_acento(normalizado) in _PAGINAS_INICIAIS:
        return True
    if _PARECE_ENDERECO.match(normalizado):
        return True
    candidatos = {"netflix", "youtube", "max", "hbo max", "disney+", "disney plus",
                  "prime video", "amazon prime video"}
    if app:
        candidatos.add(app.strip().lower())
    if platform:
        candidatos.add(platform.replace("_", " ").lower())
    return normalizado in candidatos


def _mesmo_texto(a: str, b: str) -> bool:
    return _sem_acento(a.strip().lower()) == _sem_acento(b.strip().lower())


def episodio_da_janela(
    obra: str,
    titulo_da_janela: str,
    app: str | None,
    plataforma: Platform | None,
) -> str | None:
    """O nome do episódio, quando as duas fontes nomeiam coisas diferentes.

    Medido com A Casa do Dragão no Max: a SMTC publica "A Casa do Dragão" — o
    nome da SÉRIE — enquanto a janela publica "The Treasons at Tumbleton", o do
    EPISÓDIO. É a mesma reprodução vista de dois lugares, e cada lugar sabe uma
    metade. O código só usava uma de cada vez, então a metade que sobrava era
    jogada fora: ou o cartão dizia a série e escondia o episódio, ou dizia o
    episódio e o histórico abria uma linha nova a cada um.

    Quem manda no nome da obra é a SMTC, e é isso que faz a diferença no resto
    do sistema: "Rick and Morty" é uma linha só no histórico e acha o pôster
    certo no catálogo; "Campo dos Sonhos" abre uma linha por episódio e acha o
    filme de 1989 com o mesmo nome.
    """
    if not obra or not titulo_da_janela:
        return None
    # "Home", "Netflix", um endereço: a janela está no catálogo do serviço, não
    # num episódio.
    if _titulo_generico(titulo_da_janela, app, plataforma):
        return None
    # As duas fontes dizendo o mesmo é o caso do filme: não há episódio.
    if _mesmo_texto(titulo_da_janela, obra):
        return None
    # A janela repetindo a série com algo colado ("A Casa do Dragão - T2") não
    # é o nome de um episódio, é o mesmo nome com enfeite.
    if _sem_acento(obra.lower()) in _sem_acento(titulo_da_janela.lower()):
        return None
    return titulo_da_janela


class WindowsNowPlayingReader:
    """Lê a sessão de mídia atual. Devolve None quando não há nada tocando."""

    def __init__(self, window_title_reader=None) -> None:
        # Injetável para teste e para reaproveitar o localizador de janelas que
        # já existe, sem acoplar este módulo a ele.
        self._window_title_reader = window_title_reader
        self._relogio = RelogioDaMidia()

    async def read(self) -> NowPlaying | None:
        if sys.platform != "win32":
            return None
        try:
            return await self._read_windows()
        except Exception:  # noqa: BLE001 - mídia indisponível não derruba nada
            return None

    async def _read_windows(self) -> NowPlaying | None:
        try:
            from winsdk.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as Manager,
            )
            from winsdk.windows.storage.streams import DataReader
        except ImportError:
            return None

        manager = await Manager.request_async()
        sessao = manager.get_current_session()
        if sessao is None:
            return None

        app = sessao.source_app_user_model_id or None
        info = sessao.get_playback_info()
        status = int(info.playback_status)
        if status not in (STATUS_PLAYING, STATUS_PAUSED):
            return None

        props = await sessao.try_get_media_properties_async()
        titulo = (props.title or "").strip()
        artista = (props.artist or "").strip() or None

        # O serviço, na ordem em que a resposta é mais confiável: o aplicativo
        # que publica a mídia sabe quem é; o título da SMTC costuma dizer; a
        # janela é o último recurso. Resolver antes de ler a janela é o que
        # permite pedir a janela certa quando há mais de um serviço aberto.
        plataforma = _plataforma_do_app(app) or plataforma_no_titulo(props.title)

        # A janela é lida uma vez só, e responde a três perguntas: o nome da
        # obra quando a SMTC não diz, o nome do serviço quando o aplicativo não
        # diz, e o nome do episódio quando a SMTC diz o da série.
        titulo_da_janela = self._ler_janela(plataforma)
        if plataforma is None:
            plataforma = plataforma_no_titulo(titulo_da_janela)

        da_janela_limpo = (
            limpar_titulo_de_janela(titulo_da_janela) if titulo_da_janela else ""
        )

        # O navegador só publica o nome do site; o nome do conteúdo está na
        # janela. Sem esta troca, o cartão diria "Netflix" para todo filme.
        smtc_nomeia = not _titulo_generico(titulo, app, plataforma)
        if not smtc_nomeia and da_janela_limpo:
            titulo = da_janela_limpo

        # O título entra na conta da linha do tempo porque é ele que prova de
        # quem é a posição publicada — ver `RelogioDaMidia`. O resolvido, e não
        # o cru da SMTC: no navegador o cru é sempre o nome do site, que não
        # muda quando o conteúdo muda.
        posicao, duracao, parada = _linha_do_tempo(
            sessao,
            tocando=status == STATUS_PLAYING,
            relogio=self._relogio,
            titulo=titulo or None,
        )

        # A limpeza vale para o que veio da SMTC também, e não só para o que
        # veio da janela: o Prime Video publica "Prime Video: Batman: Caped
        # Crusader" na própria API de mídia. Sem passar por aqui, esse prefixo
        # entra no histórico e vai parar na busca do pôster — que, encurtada,
        # achou um evento de boxe chamado "Prime Video Boxing".
        titulo = limpar_titulo_de_janela(titulo) or titulo

        return NowPlaying(
            title=titulo or (app or "Reproduzindo"),
            artist=artista,
            app=app,
            platform=plataforma,
            playing=status == STATUS_PLAYING,
            position_seconds=posicao,
            duration_seconds=duracao if duracao and duracao > 0 else None,
            thumbnail=await _ler_capa(props, DataReader),
            episode=(
                episodio_da_janela(titulo, da_janela_limpo, app, plataforma)
                if smtc_nomeia else None
            ),
            position_stale=parada,
        )

    def _ler_janela(self, plataforma: Platform | None) -> str | None:
        """O título da janela, de preferência a do serviço que está tocando.

        Medido com três abas de serviço abertas ao mesmo tempo — Max no Chrome,
        Netflix no Edge, Netflix no Chrome: quem procurava "uma janela de
        plataforma qualquer" achava a primeira da ordem do Windows, que não é
        a que está tocando. O nome de "Família Soprano" chegou a ser lido
        enquanto quem tocava era outra coisa, em outro serviço.
        """
        if self._window_title_reader is None:
            return None
        try:
            return self._window_title_reader(plataforma)
        except TypeError:
            # Leitor antigo, sem preferência de plataforma.
            return self._window_title_reader()


# Serviços em que o título da janela nomeia a OBRA, e não o episódio.
#
# Não é preferência, é medição — cada serviço nomeia a janela do jeito dele:
#
#   Prime Video  "Prime Video: Batman: Caped Crusader"   a obra
#   YouTube      "CHEGUEI NA SÍRIA …"                    o vídeo, que é a obra
#   Disney+      "O Justiceiro | Disney+"                a obra
#   Max          "⁨46 Long⁩ • HBO Max"                     o EPISÓDIO
#   Netflix      "Netflix - Home - Netflix"              nada, nunca o conteúdo
#
# É o que decide se uma leitura sem a SMTC pode virar histórico. Tratar todos
# igual custou os dois lados: com tudo confiável, uma tarde de Rick and Morty no
# Max virou quatro "títulos assistidos" com nome de episódio, um deles com o
# pôster do filme de 1989 que se chama igual; com nada confiável, uma hora de
# Batman no Prime Video não contou nada, e o cartão ficou sem pôster.
#
# O Disney+ estava de fora por não ter sido medido, e não por saber que era
# episódio. Medido agora, com "O Justiceiro" tocando: a janela dizia
# "O Justiceiro | Disney+ - Google Chrome" — o nome da SÉRIE, não o do
# episódio. Ele nomeia a obra, como o Prime Video, então entra.
#
# E custava caro estar fora, porque o Disney+ é justamente o serviço com que a
# SMTC pendura: `request_async()` sem retorno por minutos, que é o caso que
# `da_janela` existe para socorrer. Fora da lista, esse socorro devolvia uma
# leitura que o gravador descartava — e uma série inteira assistida no Disney+
# não aparecia em "continuar assistindo", nem contava para nada.
PLATAFORMAS_COM_OBRA_NA_JANELA: frozenset[Platform] = frozenset({
    "PRIME_VIDEO",
    "YOUTUBE",
    "DISNEY_PLUS",
})


def da_janela(
    titulo_da_janela: str | None,
    plataforma: Platform | None,
    tocando: bool | None = None,
) -> NowPlaying | None:
    """O que dá para afirmar olhando só a janela aberta.

    Serve de rede quando a SMTC não responde — medido com o Disney+ tocando e
    `request_async()` pendurado por minutos. Sem isto o cartão dizia "nada
    tocando" e, pior, os controles de reprodução ficavam desativados junto,
    porque é o cartão que diz se há o que controlar.

    O que se perde é o que só a SMTC sabe: posição, duração, capa e se está
    pausado. O que se ganha é o controle voltar a funcionar.

    Se o NOME serve como obra depende do serviço, e é por isso que
    `trustworthy` não é sempre falso — ver `PLATAFORMAS_COM_OBRA_NA_JANELA`.
    """
    if not titulo_da_janela:
        return None
    titulo = limpar_titulo_de_janela(titulo_da_janela)
    if not titulo:
        return None
    return NowPlaying(
        title=titulo,
        artist=None,
        app=None,
        platform=plataforma,
        # Se está tocando, quem responde é o áudio — ver
        # app/windows/audio_activity.py. A janela sozinha não sabe.
        #
        # O palpite antigo era "tocando", com a justificativa de que a janela
        # está aberta e o usuário está assistindo. Medido: o Chrome sem som
        # nenhum saindo, e "Batman: Caped Crusader" somando um segundo por
        # segundo até 129 minutos no catálogo. Pausado, terminado ou esquecido
        # em segundo plano, tudo virava tempo assistido.
        #
        # `None` mantém o palpite otimista, porque sem forma de medir um
        # controle que diz "pausado" para quem está assistindo é pior.
        playing=True if tocando is None else tocando,
        position_seconds=None,
        duration_seconds=None,
        thumbnail=None,
        trustworthy=plataforma in PLATAFORMAS_COM_OBRA_NA_JANELA,
    )


# O que dá para dizer da linha do tempo publicada pela SMTC.
#
#   VIVA      a posição anda, ou parou há pouco: vale projetar daqui.
#   PARADA    a posição travou, mas ainda é DESTA reprodução: o número
#             continua valendo, só não avança.
#   SUSPEITA  a posição travou e o título mudou desde então: o que está
#             publicado é de outra coisa, e não vale nada.
EstadoDaLinha = Literal["VIVA", "PARADA", "SUSPEITA"]


class RelogioDaMidia:
    """Decide o que dá para dizer da linha do tempo da SMTC.

    O Chrome agrega todas as abas numa sessão só, e ela mente: medido aqui,
    ele seguia publicando a linha do tempo de um filme do Netflix fechado
    minutos antes enquanto o título já era o de outro vídeo. A posição
    projetada ficava dentro da duração — parecia plausível — e a barra andava
    mostrando um lugar que não existe.

    O sinal que separa uma sessão viva de uma congelada é simples: numa viva a
    posição bruta muda entre leituras; numa congelada, não. Como o laço já lê
    uma vez por segundo, basta lembrar a leitura anterior.

    Mas "congelada" sozinha não distingue os dois casos que importam, e tratar
    os dois como mentira apagava a minutagem de quem estava assistindo direito:

        O site simplesmente não atualiza a linha do tempo com frequência. A
        posição publicada continua sendo a desta reprodução — velha, não
        errada. Some tudo, e o cartão fica sem minutagem nenhuma no meio de um
        filme.

        A sessão do Chrome ficou para trás e descreve outra reprodução. Aí o
        número é de outro vídeo, e mostrar é pior do que não mostrar.

    O que separa os dois é o TÍTULO: se ele mudou depois que a posição travou,
    a linha do tempo ficou falando da reprodução anterior. Se é o mesmo título
    do começo ao fim, o congelamento é do relógio, não da identidade.
    """

    # Medido: a posição bruta do Chrome não anda a cada segundo — ela dá saltos
    # a cada poucos segundos, e entre os saltos fica parada. Um limite curto
    # confundiria esse intervalo normal com congelamento, e a barra ficaria
    # piscando. Doze segundos passa longe do intervalo entre saltos e ainda
    # pega o caso real, em que a linha do tempo ficou parada por minutos.
    SEGUNDOS_ATE_DESCONFIAR = 12.0

    def __init__(self) -> None:
        self._posicao_bruta: float | None = None
        self._vista_em: float | None = None
        # O título de quando a posição foi vista andando pela última vez.
        self._titulo_da_posicao: str | None = None

    def avaliar(
        self,
        posicao_bruta: float,
        tocando: bool,
        agora: float,
        titulo: str | None = None,
    ) -> EstadoDaLinha:
        if not tocando:
            # Pausado, ficar parado é o comportamento correto.
            self._lembrar(posicao_bruta, agora, titulo)
            return "VIVA"

        if self._posicao_bruta != posicao_bruta:
            self._lembrar(posicao_bruta, agora, titulo)
            return "VIVA"

        # `is None` e não `or`: zero é falsy, e com `_vista_em` em 0.0 a conta
        # virava `agora - agora`, dando sempre "parada há zero segundos" —
        # a linha do tempo congelada nunca seria detectada.
        desde = agora if self._vista_em is None else self._vista_em
        if (agora - desde) < self.SEGUNDOS_ATE_DESCONFIAR:
            return "VIVA"

        # Travada. De quem é o número que está publicado ali?
        if titulo is not None and self._titulo_da_posicao is not None:
            return "PARADA" if titulo == self._titulo_da_posicao else "SUSPEITA"
        # Sem título para comparar não dá para inocentar: fica no comportamento
        # antigo, que é desconfiar.
        return "SUSPEITA"

    def confiavel(self, posicao_bruta: float, tocando: bool, agora: float) -> bool:
        """A linha do tempo vale para projetar daqui?

        Continua existindo porque é a pergunta que quem projeta faz. "Parada"
        não vale para projetar — o número é bom, o avanço é que não.
        """
        return self.avaliar(posicao_bruta, tocando, agora) == "VIVA"

    def _lembrar(self, posicao_bruta: float, agora: float, titulo: str | None) -> None:
        self._posicao_bruta = posicao_bruta
        self._vista_em = agora
        self._titulo_da_posicao = titulo


def posicao_extrapolada(
    posicao: float,
    duracao: float | None,
    segundos_desde_a_leitura: float,
    tocando: bool,
) -> float | None:
    """Onde a mídia está agora, a partir do instantâneo da SMTC.

    A SMTC não atualiza a posição continuamente: ela guarda um valor e o
    momento em que ele foi medido. Quem consome é que projeta o resto.

    E às vezes o instantâneo simplesmente para de ser atualizado — medido no
    Chrome, que agrega todas as abas numa sessão só: depois de trocar de vídeo,
    ele seguia dizendo "tocando" com a posição congelada num valor de minutos
    atrás. Projetar esse valor daria uma barra passando de 100%. Quando a conta
    estoura a duração, a resposta honesta é não ter barra nenhuma — uma barra
    errada é pior do que barra nenhuma.
    """
    if posicao < 0:
        return None
    projetada = posicao + (segundos_desde_a_leitura if tocando else 0.0)
    if duracao is not None and duracao > 0 and projetada > duracao:
        return None
    return projetada


def _linha_do_tempo(
    sessao, tocando: bool, relogio, titulo: str | None = None,
) -> tuple[float | None, float | None, bool]:
    """(posição, duração, parada) da reprodução atual.

    "Parada" é o terceiro estado que faltava. Antes só havia posição ou nada, e
    a linha do tempo congelada caía no nada — o cartão perdia a minutagem
    inteira no meio de um filme só porque o site demorou a publicar o próximo
    valor. Agora o número velho continua indo, marcado como velho, e quem
    desenha decide não fazê-lo avançar sozinho.
    """
    linha = sessao.get_timeline_properties()
    posicao = _segundos(getattr(linha, "position", None))
    duracao = _segundos(getattr(linha, "end_time", None))
    if duracao is not None and duracao <= 0:
        duracao = None
    if posicao is None:
        return None, duracao, False

    medido_em = getattr(linha, "last_updated_time", None)
    idade = 0.0
    if medido_em is not None:
        try:
            idade = max(0.0, (datetime.now(timezone.utc) - medido_em).total_seconds())
        except (TypeError, ValueError):
            idade = 0.0

    estado = relogio.avaliar(posicao, tocando, time.monotonic(), titulo)
    if estado == "SUSPEITA":
        return None, duracao, False
    if estado == "PARADA":
        # Sem projetar: o valor é desta reprodução, mas o relógio dela travou.
        # Projetar aqui inventaria um avanço que ninguém mediu.
        return posicao, duracao, True

    return posicao_extrapolada(posicao, duracao, idade, tocando), duracao, False


def _segundos(valor) -> float | None:
    if valor is None:
        return None
    total = getattr(valor, "total_seconds", None)
    if callable(total):
        segundos = total()
        return segundos if segundos >= 0 else None
    return None


async def _ler_capa(props, DataReader) -> bytes | None:
    referencia = getattr(props, "thumbnail", None)
    if referencia is None:
        return None
    try:
        stream = await referencia.open_read_async()
        if stream.size == 0:
            return None
        leitor = DataReader(stream)
        await leitor.load_async(stream.size)
        return bytes(leitor.read_buffer(stream.size))
    except Exception:  # noqa: BLE001 - capa é enfeite, nunca motivo de falha
        return None


def _engolir_o_resultado(tarefa: asyncio.Task) -> None:
    """Lê o resultado de uma leitura abandonada só para o asyncio não reclamar.

    Sem isto, quando a tarefa termina em erro o asyncio imprime
    "Task exception was never retrieved" no log de quem não pediu nada.

    `cancelled()` antes de `exception()` porque `exception()` RELANÇA o
    CancelledError de uma tarefa cancelada — medido, e o que aparecia no log era
    justamente um "Exception in callback" vindo daqui, dentro do desligamento.
    """
    if tarefa.cancelled():
        return
    tarefa.exception()


class LeituraEmVoo:
    """Uma leitura por vez, sem nunca cancelar a chamada do Windows.

    A primeira versão usava `asyncio.wait_for`. Ao estourar o prazo ele cancela
    a corrotina, e cancelar uma operação assíncrona do WinRT no meio a deixa
    tentando concluir numa future morta — medido, com
    `InvalidStateError: invalid state` no log e o laço de atualização morrendo
    logo depois. Um batimento chegava e nunca mais nenhum.

    Aqui a leitura nunca é interrompida: se ainda não terminou, a rodada
    simplesmente passa a vez. O laço segue solto e a chamada termina no tempo
    dela.
    """

    # Medido: a SMTC pode simplesmente parar de responder — `request_async()`
    # sem retorno por minutos, com o Disney+ tocando. Como a chamada não pode
    # ser cancelada, o que resta é parar de esperar por ela.
    SEGUNDOS_ATE_DESISTIR = 5.0

    # E, depois de desistir, tentar de novo do zero. A trava da SMTC é do
    # serviço do Windows e passa sozinha — trocar o que está tocando costuma
    # bastar. Sem uma nova tentativa, quem passava não era a trava: era o
    # aplicativo, que ficava degradado até alguém reiniciar o servidor.
    #
    # Vinte segundos porque uma chamada abandonada continua viva lá dentro:
    # tentar a cada segundo empilharia sessenta chamadas penduradas por minuto.
    SEGUNDOS_ENTRE_TENTATIVAS = 20.0

    def __init__(self, reader: WindowsNowPlayingReader) -> None:
        self._reader = reader
        self._em_voo: asyncio.Task | None = None
        self._iniciada_em: float | None = None
        self._ultimo: NowPlaying | None = None
        self._abandonada_em: float | None = None
        # Instrumentação da Fase 3. Só observa: nenhuma decisão desta classe
        # depende destes dois, e é isso que mantém o refactor não-regressivo.
        self._ultimo_sucesso: float | None = None
        self._ultima_latencia: float | None = None

    @property
    def ultimo_sucesso(self) -> float | None:
        """Relógio monotônico da última leitura que voltou. `None` = nenhuma."""
        return self._ultimo_sucesso

    @property
    def ultima_latencia(self) -> float | None:
        """Quanto a última leitura completa demorou, em segundos.

        É o número que diz se a SMTC está lenta ANTES de ela travar de vez —
        hoje só se descobre o travamento quando ele já aconteceu.
        """
        return self._ultima_latencia

    @property
    def _atrasada(self) -> bool:
        """A chamada em voo passou do prazo de espera."""
        if self._em_voo is None or self._em_voo.done() or self._iniciada_em is None:
            return False
        return (time.monotonic() - self._iniciada_em) >= self.SEGUNDOS_ATE_DESISTIR

    @property
    def travada(self) -> bool:
        """Não dá para contar com a SMTC agora — nem com a chamada em voo, nem
        com o que já foi abandonado e ainda não voltou."""
        return self._abandonada_em is not None or self._atrasada

    async def ler(self) -> NowPlaying | None:
        agora = time.monotonic()

        # Pendurada além do prazo: solta a chamada e para de contar com ela.
        # Soltar e não cancelar — cancelar uma operação do WinRT no meio a
        # deixa tentando concluir numa future morta, que foi o que matou o laço
        # de atualização quando isto usava `wait_for`.
        #
        # Vale para a tentativa nova também, e não só para a primeira: a trava
        # pode continuar, e uma condição que só olhasse "já abandonei alguma?"
        # deixaria a segunda pendurada para sempre — o mesmo defeito de antes,
        # uma tentativa depois.
        if self._em_voo is not None and self._atrasada:
            self._em_voo.add_done_callback(_engolir_o_resultado)
            self._em_voo = None
            self._iniciada_em = None
            self._abandonada_em = agora
            # Sem SMTC não há posição de que se lembrar; a próxima leitura
            # começa a linha do tempo do zero.
            self._ultimo = None

        if self._em_voo is None:
            # Depois de abandonar uma, espera antes de pedir outra.
            if (
                self._abandonada_em is not None
                and (agora - self._abandonada_em) < self.SEGUNDOS_ENTRE_TENTATIVAS
            ):
                return None
            self._em_voo = asyncio.ensure_future(self._reader.read())
            self._iniciada_em = agora

        if not self._em_voo.done():
            # Ainda lendo: devolve o último estado conhecido em vez de mentir
            # que não há nada tocando.
            return self._ultimo

        tarefa, self._em_voo = self._em_voo, None
        # Guardado antes de limpar: é daqui que sai a latência, e sem isso ela
        # seria sempre desconhecida justamente na volta bem-sucedida.
        iniciada_em, self._iniciada_em = self._iniciada_em, None
        try:
            self._ultimo = tarefa.result()
        except Exception:  # noqa: BLE001 - mídia indisponível não derruba nada
            self._ultimo = None
        else:
            # Respondeu: a SMTC voltou, e o cartão volta a ter capa e duração.
            self._abandonada_em = None
            self._ultimo_sucesso = agora
            if iniciada_em is not None:
                self._ultima_latencia = max(0.0, agora - iniciada_em)
        return self._ultimo
