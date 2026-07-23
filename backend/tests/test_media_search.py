from unittest.mock import Mock

from app.platforms.browser import BrowserLaunchResult, BrowserLauncher
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


def test_media_search_rejects_unsupported_platform_without_side_effects():
    browser = Mock(spec=BrowserLauncher)
    spotify = Mock(spec=SpotifyLauncher)
    launcher = MediaSearchLauncher(browser_launcher=browser, spotify_launcher=spotify)

    result = launcher.search("NETFLIX", "Interestelar")  # type: ignore[arg-type]

    assert result.executed is False
    assert result.error == "SEARCH_PLATFORM_NOT_ALLOWED"
    browser.open.assert_not_called()
    spotify.search.assert_not_called()
