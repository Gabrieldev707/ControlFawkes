from unittest.mock import Mock

from app.platforms.browser import BrowserLaunchResult, BrowserLauncher
from app.platforms.spotify import SpotifyLauncher


def test_spotify_launcher_prefers_installed_app_with_official_uri():
    uri_opener = Mock()
    browser = Mock(spec=BrowserLauncher)
    launcher = SpotifyLauncher(browser_launcher=browser, uri_opener=uri_opener)

    result = launcher.open()

    assert result.executed is True
    assert result.strategy == "SPOTIFY_APP"
    uri_opener.assert_called_once_with("spotify:")
    browser.open.assert_not_called()


def test_spotify_launcher_falls_back_to_official_web_player_in_chrome():
    uri_opener = Mock(side_effect=OSError("protocol unavailable"))
    browser = Mock(spec=BrowserLauncher)
    browser.open.return_value = BrowserLaunchResult(executed=True, strategy="CHROME")
    launcher = SpotifyLauncher(browser_launcher=browser, uri_opener=uri_opener)

    result = launcher.open()

    assert result.executed is True
    assert result.strategy == "SPOTIFY_WEB_CHROME"
    browser.open.assert_called_once_with("https://open.spotify.com")


def test_spotify_launcher_does_not_claim_success_when_app_and_chrome_fail():
    uri_opener = Mock(side_effect=OSError("protocol unavailable"))
    browser = Mock(spec=BrowserLauncher)
    browser.open.return_value = BrowserLaunchResult(
        executed=False,
        error="CHROME_NOT_FOUND",
    )
    launcher = SpotifyLauncher(browser_launcher=browser, uri_opener=uri_opener)

    result = launcher.open()

    assert result.executed is False
    assert result.strategy is None
    assert result.error == "CHROME_NOT_FOUND"
