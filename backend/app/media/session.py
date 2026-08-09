from collections.abc import Callable
from dataclasses import dataclass
import ctypes
import re
import sys
from typing import Literal
import unicodedata

from app.schemas.ws import Platform


MediaSessionKind = Literal["WEB", "APP"]
ForegroundTitleReader = Callable[[], str | None]
AudioProcessReader = Callable[[], list[str]]


def _read_audio_processes() -> list[str]:
    """Processos com sessão de áudio ativa no Windows."""
    if sys.platform != "win32":
        return []
    try:
        import pythoncom
        from pycaw.pycaw import AudioUtilities
    except ImportError:
        return []

    pythoncom.CoInitialize()
    try:
        names: list[str] = []
        for session in AudioUtilities.GetAllSessions():
            process = getattr(session, "Process", None)
            if process is None:
                continue
            try:
                names.append(process.name())
            except Exception:  # noqa: BLE001 - processo pode morrer no meio
                continue
        return names
    finally:
        pythoncom.CoUninitialize()


@dataclass(frozen=True)
class MediaSession:
    platform: Platform
    kind: MediaSessionKind


def _read_foreground_title() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        user32 = ctypes.windll.user32
        window = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(window)
        if not window or length <= 0:
            return None
        buffer = ctypes.create_unicode_buffer(length + 1)
        if user32.GetWindowTextW(window, buffer, len(buffer)) <= 0:
            return None
    except OSError:
        return None
    return buffer.value.strip() or None


def _normalize_title(title: str) -> str:
    decomposed = unicodedata.normalize("NFKD", title.lower())
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )


class WindowsMediaSessionDetector:
    """Identifica a plataforma de mídia ativa.

    Prioriza quem está de fato produzindo áudio; o título da janela é apenas
    fallback. O título sozinho é frágil: o Spotify Desktop mostra
    "Artista - Música" enquanto toca, e não a palavra "Spotify", então
    play/pause falhava exatamente quando havia música tocando. No Chrome, o
    título é o da aba em foco, que pode não ser a aba que toca.
    """

    def __init__(
        self,
        foreground_title_reader: ForegroundTitleReader | None = None,
        audio_process_reader: AudioProcessReader | None = None,
    ) -> None:
        self._foreground_title_reader = foreground_title_reader or _read_foreground_title
        self._audio_process_reader = audio_process_reader or _read_audio_processes

    def detect(self) -> MediaSession | None:
        by_audio = self._detect_by_audio()
        if by_audio is not None:
            return by_audio
        return self._detect_by_title()

    def _detect_by_audio(self) -> MediaSession | None:
        try:
            processes = {name.lower() for name in self._audio_process_reader()}
        except Exception:  # noqa: BLE001 - áudio indisponível não pode derrubar
            return None

        # O Spotify é identificável sozinho porque tem processo próprio.
        if "spotify.exe" in processes:
            return MediaSession(platform="SPOTIFY", kind="APP")

        # O Chrome agrupa todas as abas num processo: saber que ele toca não
        # diz qual plataforma é. Aí o título desempata.
        if "chrome.exe" in processes:
            by_title = self._detect_by_title()
            if by_title is not None:
                return by_title
        return None

    def _detect_by_title(self) -> MediaSession | None:
        title = self._foreground_title_reader()
        if not title:
            return None

        normalized = _normalize_title(title)
        platform: Platform | None = None
        if "youtube" in normalized:
            platform = "YOUTUBE"
        elif "netflix" in normalized:
            platform = "NETFLIX"
        elif "prime video" in normalized:
            platform = "PRIME_VIDEO"
        elif "disney+" in normalized or "disney plus" in normalized:
            platform = "DISNEY_PLUS"
        elif "spotify" in normalized:
            platform = "SPOTIFY"
        elif re.search(r"\bmax\b", normalized):
            platform = "MAX"

        if platform is None:
            return None
        kind: MediaSessionKind = "WEB" if "google chrome" in normalized else "APP"
        return MediaSession(platform=platform, kind=kind)
