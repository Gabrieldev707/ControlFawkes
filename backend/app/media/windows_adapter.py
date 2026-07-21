from collections.abc import Callable
import ctypes
import sys

from app.media.actions import MediaAction


KeyEvent = Callable[[int, int, int, int], None]
KEYEVENTF_KEYUP = 0x0002

MEDIA_VIRTUAL_KEYS: dict[MediaAction, int] = {
    "MEDIA_PLAY_PAUSE": 0xB3,
    "MEDIA_PREVIOUS": 0xB1,
    "MEDIA_NEXT": 0xB0,
    "MEDIA_SEEK_BACK": 0x25,
    "MEDIA_SEEK_FORWARD": 0x27,
    "MEDIA_FULLSCREEN": 0x7A,
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

    def execute(self, action: MediaAction) -> bool:
        if self._key_event is None:
            return False

        virtual_key = MEDIA_VIRTUAL_KEYS[action]
        try:
            self._key_event(virtual_key, 0, 0, 0)
            self._key_event(virtual_key, 0, KEYEVENTF_KEYUP, 0)
        except OSError:
            return False
        return True
