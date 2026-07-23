from unittest.mock import Mock

import pytest

from app.platforms.browser import BrowserLaunchResult, BrowserLauncher
from app.platforms.registry import is_browser_url_allowed
from app.platforms.search import MediaSearchLauncher
from app.platforms.spotify import SpotifyLauncher


def test_youtube_search_opens_encoded_results_page_without_selecting_a_video():
    browser = Mock(spec=BrowserLauncher)
    browser.open.return_value = BrowserLaunchResult(executed=True, strategy="CHROME")
    spotify = Mock(spec=SpotifyLauncher)
    launcher = MediaSearchLauncher(browser_launcher=browser, spotify_launcher=spotify)

    result = launcher.search("YOUTUBE", "Billie Jean do Michael Jackson")

    assert result.executed is True
    assert result.strategy == "CHROME"
    browser.open.assert_called_once_with(
        "https://www.youtube.com/results?search_query=Billie+Jean+do+Michael+Jackson"
    )
    spotify.search.assert_not_called()


def test_spotify_search_delegates_to_app_first_launcher():
    browser = Mock(spec=BrowserLauncher)
    spotify = Mock(spec=SpotifyLauncher)
    spotify.search.return_value = BrowserLaunchResult(
        executed=True,
        strategy="SPOTIFY_APP",
    )
    launcher = MediaSearchLauncher(browser_launcher=browser, spotify_launcher=spotify)

    result = launcher.search("SPOTIFY", "Runaway")

    assert result.executed is True
    assert result.strategy == "SPOTIFY_APP"
    spotify.search.assert_called_once_with("Runaway")
    browser.open.assert_not_called()


@pytest.mark.parametrize("platform", ["MAX", "DISNEY_PLUS"])
def test_media_search_rejects_unsupported_platform_without_side_effects(platform):
    """Max e Disney+ não têm URL de busca estável; ver registry.py."""
    browser = Mock(spec=BrowserLauncher)
    spotify = Mock(spec=SpotifyLauncher)
    launcher = MediaSearchLauncher(browser_launcher=browser, spotify_launcher=spotify)

    result = launcher.search(platform, "Interestelar")  # type: ignore[arg-type]

    assert result.executed is False
    assert result.error == "SEARCH_PLATFORM_NOT_ALLOWED"
    browser.open.assert_not_called()
    spotify.search.assert_not_called()


@pytest.mark.parametrize(
    ("platform", "expected_url"),
    [
        ("NETFLIX", "https://www.netflix.com/search?q=Interestelar"),
        ("PRIME_VIDEO", "https://www.primevideo.com/search?phrase=Interestelar"),
        ("YOUTUBE", "https://www.youtube.com/results?search_query=Interestelar"),
    ],
)
def test_media_search_opens_only_the_backend_built_url(platform, expected_url):
    browser = Mock(spec=BrowserLauncher)
    browser.open.return_value = BrowserLaunchResult(executed=True, strategy="CHROME")
    spotify = Mock(spec=SpotifyLauncher)
    launcher = MediaSearchLauncher(browser_launcher=browser, spotify_launcher=spotify)

    result = launcher.search(platform, "Interestelar")

    assert result.executed is True
    browser.open.assert_called_once_with(expected_url)
    spotify.search.assert_not_called()


def test_media_search_encodes_the_query_without_leaking_url_syntax():
    browser = Mock(spec=BrowserLauncher)
    browser.open.return_value = BrowserLaunchResult(executed=True, strategy="CHROME")
    launcher = MediaSearchLauncher(
        browser_launcher=browser,
        spotify_launcher=Mock(spec=SpotifyLauncher),
    )

    launcher.search("NETFLIX", "rock & roll?q=evil")

    opened = browser.open.call_args[0][0]
    assert opened == "https://www.netflix.com/search?q=rock+%26+roll%3Fq%3Devil"
    assert is_browser_url_allowed(opened) is True


@pytest.mark.parametrize("url", [
    "https://www.netflix.com/search?q=Interestelar",
    "https://www.primevideo.com/search?phrase=Interestelar",
    "https://www.youtube.com/results?search_query=Interestelar",
    "https://open.spotify.com/search/Runaway",
])
def test_allowlist_accepts_the_built_search_urls(url):
    assert is_browser_url_allowed(url) is True


@pytest.mark.parametrize("url", [
    # Plataformas sem busca estável continuam bloqueadas.
    "https://www.max.com/search?q=Interestelar",
    "https://www.hbomax.com/search?q=Interestelar",
    "https://www.disneyplus.com/search?q=Interestelar",
    # Host parecido, mas diferente.
    "https://www.netflix.com.evil.example/search?q=x",
    "https://netflix.com.evil.example/search?q=x",
    "https://evil.example/search?q=x",
    # Path fora do previsto.
    "https://www.netflix.com/browse",
    "https://www.netflix.com/search/../account?q=x",
    # Parâmetro extra ou trocado.
    "https://www.netflix.com/search?q=x&redirect=evil",
    "https://www.netflix.com/search?url=evil",
    "https://www.primevideo.com/search?q=Interestelar",
    # Consulta vazia.
    "https://www.netflix.com/search?q=",
    "https://www.netflix.com/search?q=%20",
    # Forma insegura.
    "http://www.netflix.com/search?q=x",
    "https://user:pass@www.netflix.com/search?q=x",
    "https://www.netflix.com:8443/search?q=x",
    "https://www.netflix.com/search?q=x#fragment",
])
def test_allowlist_rejects_unsupported_or_unsafe_search_urls(url):
    assert is_browser_url_allowed(url) is False
