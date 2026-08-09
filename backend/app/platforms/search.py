from typing import Literal

from app.platforms.browser import BrowserLaunchResult, BrowserLauncher
from app.platforms.registry import build_search_url
from app.platforms.spotify import SpotifyLauncher


# Somente plataformas com URL de busca estável e verificada. Max e Disney+ não
# entram: ver a nota em app/platforms/registry.py.
SearchPlatform = Literal["YOUTUBE", "SPOTIFY", "NETFLIX", "PRIME_VIDEO"]
SEARCH_PLATFORM_VALUES: tuple[SearchPlatform, ...] = (
    "YOUTUBE",
    "SPOTIFY",
    "NETFLIX",
    "PRIME_VIDEO",
)


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
        # O Spotify tem app nativo; as demais abrem no Chrome pela URL montada
        # no backend.
        if platform == "SPOTIFY":
            return self._spotify_launcher.search(query)

        url = build_search_url(platform, query)
        if url is None:
            return BrowserLaunchResult(
                executed=False,
                error="SEARCH_PLATFORM_NOT_ALLOWED",
            )
        return self._browser_launcher.open(url)
