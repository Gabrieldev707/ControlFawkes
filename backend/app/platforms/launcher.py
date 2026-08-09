from app.platforms.browser import BrowserLaunchResult, BrowserLauncher
from app.platforms.registry import BROWSER_PLATFORMS, PLATFORM_URLS
from app.platforms.spotify import SpotifyLauncher
from app.schemas.ws import Platform


class PlatformLauncher:
    def __init__(
        self,
        browser_launcher: BrowserLauncher | None = None,
        spotify_launcher: SpotifyLauncher | None = None,
    ) -> None:
        self._browser_launcher = browser_launcher or BrowserLauncher()
        self._spotify_launcher = spotify_launcher or SpotifyLauncher(
            browser_launcher=self._browser_launcher,
        )

    def open(self, platform: Platform) -> BrowserLaunchResult:
        if platform in BROWSER_PLATFORMS:
            return self._browser_launcher.open(PLATFORM_URLS[platform])

        if platform != "SPOTIFY":
            return BrowserLaunchResult(executed=False, error="PLATFORM_NOT_ALLOWED")
        return self._spotify_launcher.open()

    def open_url(self, url: str) -> BrowserLaunchResult:
        """Abre um link já validado. O launcher revalida pela allowlist."""
        return self._browser_launcher.open(url)
