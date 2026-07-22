from pathlib import Path
from unittest.mock import Mock

from app.platforms.browser import BrowserLaunchResult, BrowserLauncher, ChromeLocator
from app.platforms.launcher import PlatformLauncher
from app.platforms.registry import PLATFORM_URLS
from app.platforms.spotify import SpotifyLauncher


def test_chrome_locator_uses_standard_windows_installation_without_personal_paths():
    expected = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    locator = ChromeLocator(
        environment={"PROGRAMFILES": r"C:\Program Files"},
        which=Mock(return_value=None),
        path_exists=lambda path: path == expected,
        registry_reader=Mock(return_value=None),
    )

    assert locator.find() == expected


def test_browser_launcher_opens_only_allowlisted_platform_url_in_chrome_default_profile():
    locator = Mock(spec=ChromeLocator)
    locator.find.return_value = Path(r"C:\Chrome\chrome.exe")
    start_process = Mock()
    launcher = BrowserLauncher(locator=locator, process_starter=start_process)

    result = launcher.open("https://www.youtube.com")

    assert result.executed is True
    assert result.strategy == "CHROME"
    assert result.error is None
    start_process.assert_called_once_with([
        r"C:\Chrome\chrome.exe",
        "--new-tab",
        "https://www.youtube.com",
    ])
    assert "--user-data-dir" not in start_process.call_args.args[0]
    assert "--incognito" not in start_process.call_args.args[0]


def test_browser_launcher_rejects_arbitrary_url_before_starting_a_process():
    locator = Mock(spec=ChromeLocator)
    start_process = Mock()
    launcher = BrowserLauncher(locator=locator, process_starter=start_process)

    result = launcher.open("https://example.com/not-allowed")

    assert result.executed is False
    assert result.error == "URL_NOT_ALLOWED"
    locator.find.assert_not_called()
    start_process.assert_not_called()


def test_browser_launcher_reports_when_chrome_is_not_found():
    locator = Mock(spec=ChromeLocator)
    locator.find.return_value = None
    start_process = Mock()
    launcher = BrowserLauncher(locator=locator, process_starter=start_process)

    result = launcher.open("https://www.netflix.com")

    assert result.executed is False
    assert result.error == "CHROME_NOT_FOUND"
    start_process.assert_not_called()


def test_browser_launcher_does_not_claim_success_when_process_creation_fails():
    locator = Mock(spec=ChromeLocator)
    locator.find.return_value = Path(r"C:\Chrome\chrome.exe")
    start_process = Mock(side_effect=OSError("blocked"))
    launcher = BrowserLauncher(locator=locator, process_starter=start_process)

    result = launcher.open("https://www.max.com")

    assert result.executed is False
    assert result.error == "CHROME_LAUNCH_FAILED"


def test_platform_launcher_routes_web_platforms_through_browser_launcher():
    browser = Mock(spec=BrowserLauncher)
    browser.open.return_value = BrowserLaunchResult(executed=True, strategy="CHROME")
    spotify = Mock(spec=SpotifyLauncher)
    launcher = PlatformLauncher(browser_launcher=browser, spotify_launcher=spotify)

    platforms = ("YOUTUBE", "NETFLIX", "MAX", "PRIME_VIDEO", "DISNEY_PLUS")
    for platform in platforms:
        result = launcher.open(platform)
        assert result.executed is True
        assert result.strategy == "CHROME"

    assert browser.open.call_args_list == [
        ((PLATFORM_URLS[platform],), {}) for platform in platforms
    ]
    spotify.open.assert_not_called()


def test_platform_launcher_routes_spotify_through_app_first_launcher():
    browser = Mock(spec=BrowserLauncher)
    spotify = Mock(spec=SpotifyLauncher)
    spotify.open.return_value = BrowserLaunchResult(
        executed=True,
        strategy="SPOTIFY_APP",
    )
    launcher = PlatformLauncher(browser_launcher=browser, spotify_launcher=spotify)

    result = launcher.open("SPOTIFY")

    assert result.executed is True
    assert result.strategy == "SPOTIFY_APP"
    spotify.open.assert_called_once_with()
    browser.open.assert_not_called()
