from typing import Literal
from urllib.parse import urlencode

from app.platforms.browser import BrowserLaunchResult, BrowserLauncher
from app.platforms.spotify import SpotifyLauncher


SearchPlatform = Literal["YOUTUBE", "SPOTIFY"]


class MediaSearchLauncher:
    def __init__(
        self,
        browser_launcher: BrowserLauncher | None = None,
        spotify_launcher: SpotifyLauncher | None = None,
    ) -> None:
        self._browser_launcher = browser_launcher or BrowserLauncher()
        self._spotify_launcher = spotify_launcher or SpotifyLauncher(
            browser_launcher=self._browser_launcher,
        )

    def search(
        self,
        platform: SearchPlatform,
        query: str,
    ) -> BrowserLaunchResult:
        if platform == "YOUTUBE":
            encoded = urlencode({"search_query": query})
            return self._browser_launcher.open(
                f"https://www.youtube.com/results?{encoded}"
            )
        if platform == "SPOTIFY":
            return self._spotify_launcher.search(query)
        return BrowserLaunchResult(
            executed=False,
            error="SEARCH_PLATFORM_NOT_ALLOWED",
        )
