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
    def __init__(
        self,
        foreground_title_reader: ForegroundTitleReader | None = None,
    ) -> None:
        self._foreground_title_reader = foreground_title_reader or _read_foreground_title

    def detect(self) -> MediaSession | None:
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
