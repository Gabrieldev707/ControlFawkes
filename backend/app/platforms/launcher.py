from collections.abc import Callable
import webbrowser

from app.platforms.registry import PLATFORM_URLS
from app.schemas.ws import Platform


BrowserOpener = Callable[..., bool]


class PlatformLauncher:
    def __init__(self, opener: BrowserOpener | None = None) -> None:
        self._opener = opener or webbrowser.open

    def open(self, platform: Platform) -> bool:
        try:
            return bool(
                self._opener(
                    PLATFORM_URLS[platform],
                    new=2,
                    autoraise=True,
                )
            )
        except (KeyError, OSError, webbrowser.Error):
            return False
