from collections.abc import Callable, Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Literal

from app.platforms.registry import is_browser_url_allowed


ChromeError = str
LaunchStrategy = Literal["CHROME", "SPOTIFY_APP", "SPOTIFY_WEB_CHROME"]
PathExists = Callable[[Path], bool]
RegistryReader = Callable[[], Path | None]
WhichExecutable = Callable[[str], str | None]
ProcessStarter = Callable[[list[str]], object]


@dataclass(frozen=True)
class BrowserLaunchResult:
    executed: bool
    strategy: LaunchStrategy | None = None
    error: ChromeError | None = None


def _read_chrome_app_path() -> Path | None:
    if sys.platform != "win32":
        return None

    try:
        import winreg
    except ImportError:
        return None

    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(
                hive,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
            ) as key:
                value, _ = winreg.QueryValueEx(key, None)
        except OSError:
            continue
        if isinstance(value, str) and value.strip():
            return Path(value.strip().strip('"'))
    return None


class ChromeLocator:
    def __init__(
        self,
        environment: Mapping[str, str] | None = None,
        which: WhichExecutable | None = None,
        path_exists: PathExists | None = None,
        registry_reader: RegistryReader | None = None,
    ) -> None:
        self._environment = environment if environment is not None else os.environ
        self._which = which or shutil.which
        self._path_exists = path_exists or Path.is_file
        self._registry_reader = registry_reader or _read_chrome_app_path

    def find(self) -> Path | None:
        registered = self._registry_reader()
        if registered is not None and self._path_exists(registered):
            return registered

        for executable in ("chrome.exe", "chrome"):
            discovered = self._which(executable)
            if discovered:
                path = Path(discovered)
                if self._path_exists(path):
                    return path

        candidates = (
            ("LOCALAPPDATA", Path("Google/Chrome/Application/chrome.exe")),
            ("PROGRAMFILES", Path("Google/Chrome/Application/chrome.exe")),
            ("PROGRAMFILES(X86)", Path("Google/Chrome/Application/chrome.exe")),
        )
        for variable, suffix in candidates:
            root = self._environment.get(variable)
            if not root:
                continue
            path = Path(root) / suffix
            if self._path_exists(path):
                return path
        return None


def _start_process(command: list[str]) -> object:
    return subprocess.Popen(command, close_fds=True)


class BrowserLauncher:
    def __init__(
        self,
        locator: ChromeLocator | None = None,
        process_starter: ProcessStarter | None = None,
    ) -> None:
        self._locator = locator or ChromeLocator()
        self._process_starter = process_starter or _start_process

    def open(self, url: str) -> BrowserLaunchResult:
        if not is_browser_url_allowed(url):
            return BrowserLaunchResult(executed=False, error="URL_NOT_ALLOWED")

        chrome = self._locator.find()
        if chrome is None:
            return BrowserLaunchResult(executed=False, error="CHROME_NOT_FOUND")

        try:
            self._process_starter([str(chrome), "--new-tab", url])
        except OSError:
            return BrowserLaunchResult(executed=False, error="CHROME_LAUNCH_FAILED")
        return BrowserLaunchResult(executed=True, strategy="CHROME")
