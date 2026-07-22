from collections.abc import Callable
import webbrowser

from app.platforms.browser import BrowserLaunchResult, BrowserLauncher
from app.platforms.registry import BROWSER_PLATFORMS, PLATFORM_URLS
from app.schemas.ws import Platform


BrowserOpener = Callable[..., bool]


class PlatformLauncher:
    def __init__(
        self,
        browser_launcher: BrowserLauncher | None = None,
        spotify_opener: BrowserOpener | None = None,
    ) -> None:
        self._browser_launcher = browser_launcher or BrowserLauncher()
        self._spotify_opener = spotify_opener or webbrowser.open

    def open(self, platform: Platform) -> BrowserLaunchResult:
        if platform in BROWSER_PLATFORMS:
            return self._browser_launcher.open(PLATFORM_URLS[platform])

        if platform != "SPOTIFY":
            return BrowserLaunchResult(executed=False, error="PLATFORM_NOT_ALLOWED")

        try:
            executed = bool(
                self._spotify_opener(
                    PLATFORM_URLS[platform],
                    new=2,
                    autoraise=True,
                )
            )
        except (KeyError, OSError, webbrowser.Error):
            executed = False
        return BrowserLaunchResult(
            executed=executed,
            strategy="DEFAULT_BROWSER" if executed else None,
            error=None if executed else "SPOTIFY_LAUNCH_FAILED",
        )
