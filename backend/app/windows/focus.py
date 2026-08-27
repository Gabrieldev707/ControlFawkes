"""Encontrar e trazer para frente a janela da plataforma.

Por que isto existe: `keybd_event` e `SendInput` entregam a tecla para a janela
em primeiro plano, seja ela qual for. Sem este módulo, "tela cheia" digitava um
"f" no Visual Studio Code se ele estivesse na frente, "+10s" mandava seta para
o Explorer, e o controle respondia "comando enviado" em todos os casos — porque
a tecla realmente foi enviada, só não para onde o usuário queria.

O detector de sessão tinha o mesmo ponto cego: lia só o título da janela da
frente. Com a página do controle aberta no próprio computador, ele não achava
o Max que estava tocando atrás e respondia "nenhuma plataforma ativa".
"""

from collections.abc import Callable
from dataclasses import dataclass
import ctypes
import re
import sys
import unicodedata

from ctypes import wintypes

from app.schemas.ws import Platform


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SW_RESTORE = 9


@dataclass(frozen=True)
class DesktopWindow:
    handle: int
    process: str
    title: str


WindowLister = Callable[[], list[DesktopWindow]]


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


# Processo próprio: identificação direta, sem depender do título.
PLATFORM_PROCESSES: dict[Platform, str] = {"SPOTIFY": "spotify.exe"}

# Plataformas de navegador: o título da aba é o que identifica. Padrões em
# ordem — o primeiro que casar vence, e "prime video" precisa vir antes de
# qualquer coisa mais curta que também casaria.
# O espaço é opcional porque nem sempre o título é a frase bonita do serviço:
# enquanto a página carrega, e quando ninguém está logado, o Chrome mostra o
# domínio cru. Medido com as quatro abertas ao mesmo tempo — "play.hbomax.com"
# não casava com "hbo max" nem com "max" isolado (o "max" está colado no "hbo",
# então não há fronteira de palavra), e o controle respondia que o Max não
# estava aberto. O mesmo valia para "primevideo.com" e "disneyplus.com".
#
# Netflix e YouTube escapavam por sorte: o nome deles é uma palavra só, e o
# domínio a contém inteira.
PLATFORM_TITLE_PATTERNS: tuple[tuple[Platform, re.Pattern[str]], ...] = (
    ("PRIME_VIDEO", re.compile(r"prime\s*video")),
    ("DISNEY_PLUS", re.compile(r"disney\s*\+|disney\s*plus")),
    ("NETFLIX", re.compile(r"netflix")),
    ("YOUTUBE", re.compile(r"youtube")),
    # "max" solto casaria com "Max Richter" e com qualquer janela que tenha a
    # palavra; exigir "hbo max" ou "max" isolado no fim reduz o falso positivo.
    ("MAX", re.compile(r"hbo\s*max|\bmax\b")),
)


def _process_name(pid: int) -> str:
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(260)
        size = wintypes.DWORD(260)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value.rsplit("\\", 1)[-1].lower()
        return ""
    finally:
        kernel32.CloseHandle(handle)


def list_windows() -> list[DesktopWindow]:
    """Janelas visíveis com título, com o processo dono de cada uma."""
    if sys.platform != "win32":
        return []

    user32 = ctypes.windll.user32
    found: list[DesktopWindow] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def collect(handle, _lparam):
        if not user32.IsWindowVisible(handle):
            return True
        length = user32.GetWindowTextLengthW(handle)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(handle, buffer, length + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        found.append(DesktopWindow(int(handle), _process_name(pid.value), buffer.value))
        return True

    try:
        user32.EnumWindows(callback_type(collect), 0)
    except OSError:
        return []
    return found


def _pagina_do_servico(window: DesktopWindow) -> bool:
    """A janela mostra o catálogo do serviço, não uma obra.

    "Home - Netflix", "Netflix", "play.hbomax.com": a mesma regra que impede
    esses nomes de virarem títulos assistidos serve para escolher entre janelas
    — a que tem um nome de verdade está mais perto de ser a que toca.

    Importado aqui dentro, e não no topo, para não amarrar o localizador de
    janelas ao módulo de mídia: quem depende de quem é o contrário.
    """
    from app.media.now_playing import _titulo_generico, limpar_titulo_de_janela

    limpo = limpar_titulo_de_janela(window.title)
    return _titulo_generico(limpo, None, platform_of(window))


# Onde um serviço de streaming PODE estar. Fora daqui, o nome dele num título
# de janela é assunto, não reprodução.
#
# Medido em 25/08/2026, no `historico.json` deste computador:
#
#     NETFLIX::netflix problemas de int... - fawkes-control - visual studio code
#
# É a janela do VS Code. O título tinha a palavra "netflix" — um arquivo aberto
# sobre o assunto — e o padrão casava em qualquer janela, sem perguntar de quem
# ela era. O estrago não parou no histórico: como esse título PARECE um nome de
# obra, `media_window` o preferia à aba de verdade, e o cartão anunciava o
# editor de código como o que estava tocando.
#
# E não é só o editor. Qualquer janela com o nome de um serviço no título entra:
# um bloco de notas, um cliente de e-mail, uma pasta chamada "Netflix" no
# Explorer, esta própria conversa aberta num terminal.
#
# A regra que fecha isso não é uma lista de exceções — seria uma corrida
# perdida, e faltaria sempre uma. É a inversa: um serviço de navegador só existe
# DENTRO de um navegador. O Spotify já era identificado pelo processo dele
# próprio, e este é o mesmo princípio aplicado ao resto.
NAVEGADORES: frozenset[str] = frozenset({
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
    "vivaldi.exe",
    "arc.exe",
})


def platform_of(window: DesktopWindow) -> Platform | None:
    if window.process == PLATFORM_PROCESSES["SPOTIFY"]:
        return "SPOTIFY"

    # Processo desconhecido (string vazia) NÃO é motivo para recusar: a
    # consulta pode falhar por permissão, e recusar aí calaria uma janela
    # legítima. O que se recusa é o processo conhecido que não é navegador —
    # aí a resposta não é "não sei", é "não é".
    if window.process and window.process.lower() not in NAVEGADORES:
        return None

    title = _normalize(window.title)
    for platform, pattern in PLATFORM_TITLE_PATTERNS:
        if pattern.search(title):
            return platform
    return None


class WindowFocuser:
    def __init__(self, window_lister: WindowLister | None = None) -> None:
        self._list_windows = window_lister or list_windows

    def find(self, platform: Platform) -> DesktopWindow | None:
        """Janela da plataforma, olhando o desktop inteiro.

        A janela do próprio controle é ignorada: com a página aberta no
        computador, o título "Control Fawkes" nunca pode ser confundido com uma
        plataforma, e focá-la roubaria o foco de quem está assistindo.

        MESMO seletor que `media_window`, e é aí que estava o defeito. Este
        método escolhia "a primeira da ordem do `EnumWindows`" enquanto o
        cartão de "tocando agora" usava `media_window`, que prefere a janela
        que NOMEIA alguma coisa. Dois seletores diferentes para a mesma
        pergunta — e a ordem do `EnumWindows` é a ordem Z, que muda toda vez
        que alguma coisa ganha o foco.

        O sintoma medido: apertar "tela cheia" foca uma janela, a ordem Z vira,
        e o play/pause seguinte mandava o `SPACE` para OUTRA aba do mesmo
        serviço. Sem erro nenhum, porque a tecla foi enviada de verdade — só
        não para onde o cartão dizia que estava tocando. "Funciona e depois não
        funciona mais" é isso, e não é intermitência: é o desempate mudando.
        """
        return self.media_window(platform)

    def focus(self, window: DesktopWindow) -> bool:
        """Traz a janela para frente.

        O Windows só deixa trocar o primeiro plano a partir do processo que já
        está lá. Anexar a fila de entrada da thread dona do foco é o caminho
        suportado para uma ferramenta de automação fazer isso.
        """
        if sys.platform != "win32":
            return False

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        handle = window.handle
        try:
            if user32.IsIconic(handle):
                user32.ShowWindow(handle, SW_RESTORE)

            current = user32.GetForegroundWindow()
            if current == handle:
                return True

            mine = kernel32.GetCurrentThreadId()
            theirs = user32.GetWindowThreadProcessId(current, None)
            attached = bool(theirs) and theirs != mine
            if attached:
                user32.AttachThreadInput(theirs, mine, True)
            try:
                user32.BringWindowToTop(handle)
                user32.SetForegroundWindow(handle)
            finally:
                if attached:
                    user32.AttachThreadInput(theirs, mine, False)

            return user32.GetForegroundWindow() == handle
        except OSError:
            return False

    def focus_platform(self, platform: Platform) -> bool:
        window = self.find(platform)
        if window is None:
            return False
        return self.focus(window)

    def media_window(self, platform: Platform | None = None) -> DesktopWindow | None:
        """A janela que provavelmente está tocando.

        Com `platform`, só as daquele serviço — é o caso de quem já sabe quem
        está tocando pela API de mídia e só quer o nome que falta.

        Entre as candidatas, a que nomeia alguma coisa vence a que mostra a
        página inicial do serviço. Medido com três abas abertas — Max no
        Chrome, Netflix no Edge, Netflix no Chrome: "a primeira que aparecer"
        devolvia a home da Netflix, e o cartão ficava mudo enquanto o Max
        tocava logo ali do lado.
        """
        candidatas = [
            janela for janela in self._list_windows()
            if platform_of(janela) is not None
            and (platform is None or platform_of(janela) == platform)
            # A janela do próprio controle nunca é candidata. `find` já a
            # excluía e `media_window` não — e agora que os dois são o mesmo
            # seletor, a exclusão precisa valer para os dois. Sem isto, a
            # página do controle aberta no computador podia virar o alvo do
            # play/pause, roubando o foco de quem está assistindo.
            and "control fawkes" not in _normalize(janela.title)
        ]
        for janela in candidatas:
            if not _pagina_do_servico(janela):
                return janela
        return candidatas[0] if candidatas else None

    def media_window_title(self, platform: Platform | None = None) -> str | None:
        """Título da janela que provavelmente está tocando.

        Serve ao cartão de "tocando agora": o navegador publica só o nome do
        serviço na API de mídia do Windows, e o nome do conteúdo está aqui.
        """
        janela = self.media_window(platform)
        return janela.title if janela is not None else None

    def center_of(self, window: DesktopWindow) -> tuple[int, int] | None:
        """Meio da janela — onde o vídeo fica em qualquer player web."""
        if sys.platform != "win32":
            return None
        rect = wintypes.RECT()
        try:
            if not ctypes.windll.user32.GetWindowRect(window.handle, ctypes.byref(rect)):
                return None
        except OSError:
            return None
        if rect.right <= rect.left or rect.bottom <= rect.top:
            return None
        return ((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
