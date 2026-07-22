from collections.abc import Callable
import ctypes
import sys

from app.media.actions import MediaAction
from app.schemas.ws import Platform


KeyEvent = Callable[[int, int, int, int], None]
KEYEVENTF_KEYUP = 0x0002

MEDIA_VIRTUAL_KEYS: dict[Platform, dict[MediaAction, int]] = {
    "YOUTUBE": {
        "MEDIA_PLAY_PAUSE": 0xB3,
        "MEDIA_PREVIOUS": 0xB1,
        "MEDIA_NEXT": 0xB0,
        "MEDIA_SEEK_BACK": 0x4A,
        "MEDIA_SEEK_FORWARD": 0x4C,
        "MEDIA_FULLSCREEN": 0x46,
        "MEDIA_EXIT_FULLSCREEN": 0x1B,
    },
    "SPOTIFY": {
        "MEDIA_PLAY_PAUSE": 0xB3,
        "MEDIA_PREVIOUS": 0xB1,
        "MEDIA_NEXT": 0xB0,
    },
}

for _platform in ("NETFLIX", "MAX", "PRIME_VIDEO", "DISNEY_PLUS"):
    MEDIA_VIRTUAL_KEYS[_platform] = {
        "MEDIA_PLAY_PAUSE": 0xB3,
        "MEDIA_SEEK_BACK": 0x25,
        "MEDIA_SEEK_FORWARD": 0x27,
        "MEDIA_FULLSCREEN": 0x46,
        "MEDIA_EXIT_FULLSCREEN": 0x1B,
    }


class WindowsMediaAdapter:
    def __init__(self, key_event: KeyEvent | None = None) -> None:
        if key_event is not None:
            self._key_event: KeyEvent | None = key_event
        elif sys.platform == "win32":
            self._key_event = ctypes.windll.user32.keybd_event
        else:
            self._key_event = None

    def supports(self, action: MediaAction, platform: Platform) -> bool:
        return action in MEDIA_VIRTUAL_KEYS[platform]

    def execute(self, action: MediaAction, platform: Platform) -> bool:
        if self._key_event is None:
            return False

        virtual_key = MEDIA_VIRTUAL_KEYS[platform].get(action)
        if virtual_key is None:
            return False
        try:
            self._key_event(virtual_key, 0, 0, 0)
            self._key_event(virtual_key, 0, KEYEVENTF_KEYUP, 0)
        except OSError:
            return False
        return True
