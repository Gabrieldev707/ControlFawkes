from collections.abc import Callable
import os

from app.platforms.browser import BrowserLaunchResult, BrowserLauncher
from app.platforms.registry import PLATFORM_URLS


UriOpener = Callable[[str], object]


def _open_uri(uri: str) -> object:
    startfile = getattr(os, "startfile", None)
    if startfile is None:
        raise OSError("Spotify URI protocol is unavailable")
    return startfile(uri)


class SpotifyLauncher:
    def __init__(
        self,
        browser_launcher: BrowserLauncher | None = None,
        uri_opener: UriOpener | None = None,
    ) -> None:
        self._browser_launcher = browser_launcher or BrowserLauncher()
        self._uri_opener = uri_opener or _open_uri

    def open(self) -> BrowserLaunchResult:
        try:
            self._uri_opener("spotify:")
        except OSError:
            browser_result = self._browser_launcher.open(PLATFORM_URLS["SPOTIFY"])
            if not browser_result.executed:
                return browser_result
            return BrowserLaunchResult(
                executed=True,
                strategy="SPOTIFY_WEB_CHROME",
            )
        return BrowserLaunchResult(executed=True, strategy="SPOTIFY_APP")
