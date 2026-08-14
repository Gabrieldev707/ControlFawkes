from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.schemas.auth import AuthMessage, PairDeviceMessage
from app.media.actions import MediaAction
from app.schemas.volume import (
    VolumeAction,
    VolumeDeltaMessage,
    VolumeGetMessage,
    VolumeMuteToggleMessage,
    VolumeSetMessage,
)
from app.schemas.pointer import (
    PointerAction,
    PointerClickMessage,
    PointerDoubleClickMessage,
    PointerDownMessage,
    PointerMoveMessage,
    PointerRightClickMessage,
    PointerScrollMessage,
    PointerUpMessage,
)
from app.schemas.keyboard import KeyboardAction, KeyboardKeyMessage, KeyboardTextMessage
from app.schemas.navigation import NavigationAction, NavigationMessage
# Reexportados: moram em `platform.py` para as mensagens da tela poderem
# usá-los sem fechar um ciclo de importação com este módulo.
from app.schemas.platform import Platform, SearchablePlatform
from app.schemas.screen import ProfileSelectMessage, ScreenCommandData, ScreenTapMessage


ProtocolVersion = Literal[1]
# LOCAL: só o aplicativo. GLOBAL: o volume do Windows inteiro.
VolumeScope = Literal["LOCAL", "GLOBAL"]
LaunchStrategy = Literal["CHROME", "SPOTIFY_APP", "SPOTIFY_WEB_CHROME"]
ServerState = Literal["AUTH_REQUIRED", "PAIRING", "READY", "BUSY"]
ErrorCode = Literal[
    "INVALID_JSON",
    "INVALID_PAYLOAD",
    "UNSUPPORTED_MESSAGE",
    "NOT_IMPLEMENTED",
    "UNKNOWN_COMMAND",
    "UNAUTHORIZED",
    "INVALID_TOKEN",
    "PAIRING_REQUIRED",
    "PIN_INVALID",
    "PIN_EXPIRED",
    "TOO_MANY_ATTEMPTS",
    "PROTOCOL_VERSION_MISMATCH",
    "PLATFORM_OPEN_FAILED",
    "MEDIA_SEARCH_FAILED",
    "MEDIA_LINK_FAILED",
    "MEDIA_CONTROL_FAILED",
    "MEDIA_SESSION_NOT_FOUND",
    "MEDIA_ACTION_UNSUPPORTED",
    "SYSTEM_VOLUME_FAILED",
    "POINTER_CONTROL_FAILED",
    "POINTER_RATE_LIMITED",
    "RATE_LIMITED",
    "KEYBOARD_CONTROL_FAILED",
    "NAVIGATION_FAILED",
    "NAVIGATION_RATE_LIMITED",
    # Tela: a janela não está aberta, ou o perfil cadastrado sumiu.
    "SCREEN_CONTROL_FAILED",
    "PROFILE_NOT_FOUND",
    "INTERNAL_ERROR",
]


class PlatformSelectedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: Platform
    # Escolhida a partir de uma consulta que a plataforma não aceita por URL:
    # cai na tela de busca dela em vez da home, para o texto poder ser
    # digitado de imediato.
    openSearch: bool = False


class TextCommandPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=500)


class PlatformSelectedMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: ProtocolVersion
    type: Literal["PLATFORM_SELECTED"]
    requestId: str = Field(min_length=1, max_length=128)
    payload: PlatformSelectedPayload


class TextCommandMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: ProtocolVersion
    type: Literal["TEXT_COMMAND"]
    requestId: str = Field(min_length=1, max_length=128)
    payload: TextCommandPayload


class SearchMediaPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    platform: SearchablePlatform
    query: str = Field(min_length=1, max_length=200)


class SearchMediaMessage(BaseModel):
    """Busca com plataforma já escolhida pelo usuário.

    O cliente manda plataforma e consulta; a URL é montada no backend.
    """

    model_config = ConfigDict(extra="forbid")

    protocolVersion: ProtocolVersion
    type: Literal["SEARCH_MEDIA"]
    requestId: str = Field(min_length=1, max_length=128)
    payload: SearchMediaPayload


class MediaControlMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: ProtocolVersion
    type: MediaAction
    requestId: str = Field(min_length=1, max_length=128)


ClientMessage = Annotated[
    AuthMessage
    | PairDeviceMessage
    | PlatformSelectedMessage
    | TextCommandMessage
    | SearchMediaMessage
    | MediaControlMessage
    | VolumeGetMessage
    | VolumeSetMessage
    | VolumeDeltaMessage
    | VolumeMuteToggleMessage
    | PointerMoveMessage
    | PointerClickMessage
    | PointerDoubleClickMessage
    | PointerRightClickMessage
    | PointerScrollMessage
    | PointerDownMessage
    | PointerUpMessage
    | KeyboardTextMessage
    | KeyboardKeyMessage
    | NavigationMessage
    | ScreenTapMessage
    | ProfileSelectMessage,
    Field(discriminator="type"),
]


class StateUpdateMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: ProtocolVersion = 1
    type: Literal["STATE_UPDATE"] = "STATE_UPDATE"
    state: ServerState
    message: str


class PlatformCommandData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["OPEN_PLATFORM"] = "OPEN_PLATFORM"
    platform: Platform
    executed: Literal[True] = True
    strategy: LaunchStrategy


class SearchMediaCommandData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["SEARCH_MEDIA"] = "SEARCH_MEDIA"
    platform: SearchablePlatform
    executed: Literal[True] = True
    strategy: LaunchStrategy


class HelpCommandData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["SHOW_HELP"] = "SHOW_HELP"
    commands: list[str]
    executed: Literal[False] = False


class MediaCommandData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["MEDIA_CONTROL"] = "MEDIA_CONTROL"
    action: MediaAction
    platform: Platform
    session: Literal["WEB", "APP"]
    # Se a janela da plataforma foi trazida para frente antes da tecla. Quando
    # é falso, a tecla saiu mas pode ter caído em outra janela — e a interface
    # precisa poder dizer isso em vez de afirmar sucesso.
    focused: bool = True
    executed: Literal[True] = True


class VolumeCommandData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["SYSTEM_VOLUME"] = "SYSTEM_VOLUME"
    action: VolumeAction
    level: StrictInt = Field(ge=0, le=100)
    muted: bool
    # Em que escopo a mudança aconteceu de fato. O fallback para o volume do
    # Windows nunca é silencioso: a interface precisa poder dizer a verdade.
    scope: VolumeScope = "GLOBAL"
    target: str | None = None
    executed: Literal[True] = True


class PointerCommandData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["POINTER_CONTROL"] = "POINTER_CONTROL"
    action: PointerAction
    executed: Literal[True] = True


class KeyboardCommandData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["KEYBOARD_CONTROL"] = "KEYBOARD_CONTROL"
    action: KeyboardAction
    executed: Literal[True] = True


class MediaLinkCommandData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["OPEN_ALLOWED_MEDIA_LINK"] = "OPEN_ALLOWED_MEDIA_LINK"
    platform: Literal["YOUTUBE"]
    executed: Literal[True] = True
    strategy: LaunchStrategy


class NavigationCommandData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["NAVIGATION"] = "NAVIGATION"
    action: NavigationAction
    executed: Literal[True] = True


class CommandResultMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: ProtocolVersion = 1
    type: Literal["COMMAND_RESULT"] = "COMMAND_RESULT"
    requestId: str
    success: Literal[True] = True
    message: str
    data: (
        PlatformCommandData
        | SearchMediaCommandData
        | HelpCommandData
        | MediaCommandData
        | VolumeCommandData
        | PointerCommandData
        | KeyboardCommandData
        | NavigationCommandData
        | MediaLinkCommandData
        | ScreenCommandData
    )


class HeartbeatMessage(BaseModel):
    """Sinal de vida periódico, do servidor para quem já se autenticou.

    O ping do próprio protocolo WebSocket é respondido pelo navegador sem
    passar pelo JavaScript, então a página não tem como saber que ele parou.
    Quando o Wi-Fi troca de rede ou o celular dorme, a conexão pode ficar
    meio aberta: o `onclose` nunca dispara e o controle segue mostrando
    "conectado" enquanto nenhum comando chega do outro lado.

    Uma mensagem visível resolve isso: se ela para de chegar, a página sabe
    que a conexão morreu e reconecta em vez de mentir.
    """

    model_config = ConfigDict(extra="forbid")

    protocolVersion: ProtocolVersion = 1
    type: Literal["HEARTBEAT"] = "HEARTBEAT"


class NowPlayingMessage(BaseModel):
    """O que está tocando, empurrado sem o celular pedir.

    `session` nulo quer dizer "nada tocando" — é um estado legítimo e precisa
    chegar, senão o cartão anterior ficaria congelado na tela depois de o filme
    acabar.

    A posição vem uma vez por mudança, não a cada segundo: o celular conta
    sozinho a partir de `positionSeconds`. Empurrar o relógio pela rede gastaria
    uma mensagem por segundo por dispositivo para dizer o óbvio.
    """

    model_config = ConfigDict(extra="forbid")

    protocolVersion: ProtocolVersion = 1
    type: Literal["NOW_PLAYING"] = "NOW_PLAYING"
    session: "NowPlayingSession | None" = None


class NowPlayingSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    # O episódio, quando o título é o de uma série. Separado porque o cartão
    # quer mostrar os dois — "Rick and Morty" e, embaixo, "Campo dos Sonhos" —
    # enquanto o histórico e o catálogo só têm o que fazer com a série.
    episode: str | None = None
    artist: str | None = None
    app: str | None = None
    platform: Platform | None = None
    playing: bool
    positionSeconds: float | None = None
    durationSeconds: float | None = None
    # A posição é desta reprodução, mas o site parou de atualizá-la. O celular
    # mostra o número e para de contar sozinho a partir dele — sem isto, ou a
    # minutagem sumia inteira, ou ela avançava inventando um tempo que não
    # passou. Ver `RelogioDaMidia`.
    positionStale: bool = False
    # Identidade da capa publicada pelo próprio aplicativo — o Spotify manda,
    # o Chrome não. A imagem vem por HTTP, porque alguns milhares de bytes em
    # base64 estourariam o limite de mensagem.
    thumbnailId: str | None = None
    # Pôster do catálogo, para quando o aplicativo não publica capa nenhuma:
    # é o caso de todo filme assistido pelo navegador.
    posterUrl: str | None = None


class TitleAvailabilityData(BaseModel):
    """O que o catálogo sabe sobre o título pedido.

    Existe para a escolha deixar de ser um chute: em vez de listar seis
    plataformas, o controle diz em qual delas o título está.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    year: StrictInt | None = None
    posterUrl: str | None = None
    platforms: list[Platform] = Field(default_factory=list)
    # "MOVIE" ou "TV": deixa a tela perguntar em vez de escolher sozinha
    # quando filme e série respondem igualmente bem à consulta.
    kind: Literal["MOVIE", "TV"] = "MOVIE"


class NeedsPlatformMessage(BaseModel):
    """Consulta entendida, mas sem plataforma: o usuário escolhe onde procurar.

    Duas listas separadas porque as duas levam a ações diferentes:
    `suggestedPlatforms` recebe a consulta e cai direto na busca;
    `openOnlyPlatforms` só abre a plataforma, porque Max e Disney+ não têm URL
    de busca estável. A separação é o que permite oferecer as duas sem prometer
    o que não dá para cumprir.
    """

    model_config = ConfigDict(extra="forbid")

    protocolVersion: ProtocolVersion = 1
    type: Literal["NEEDS_PLATFORM"] = "NEEDS_PLATFORM"
    requestId: str
    query: str = Field(min_length=1, max_length=200)
    suggestedPlatforms: list[SearchablePlatform] = Field(min_length=1)
    openOnlyPlatforms: list[Platform] = Field(default_factory=list)
    # Ausente quando o catálogo está desligado ou não achou nada. As duas
    # listas acima continuam valendo nesse caso: o catálogo acrescenta, nunca
    # substitui o caminho manual.
    availability: TitleAvailabilityData | None = None
    # A outra leitura do mesmo nome. "O Justiceiro" é filme de 2004 no Max
    # e série da Marvel no Disney+; adivinhar erraria metade das vezes.
    availabilityAlternative: TitleAvailabilityData | None = None


class ErrorMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: ProtocolVersion = 1
    type: Literal["ERROR"] = "ERROR"
    requestId: str
    code: ErrorCode
    message: str


# `NowPlayingSession` é declarada depois de quem a usa, para a mensagem ficar
# no topo; o rebuild resolve a referência adiada.
NowPlayingMessage.model_rebuild()
