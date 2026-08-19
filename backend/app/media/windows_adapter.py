from collections.abc import Callable
import ctypes
import sys

from app.input.teclas import flags_de, scan_code_de
from app.media.actions import MediaAction
from app.schemas.ws import Platform


KeyEvent = Callable[[int, int, int, int], None]

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
        # Scan code e flag de tecla estendida: sem eles, seta-esquerda chega
        # como o 4 do teclado numérico e o player web ignora. Ver
        # `app/input/teclas.py` — foi o que quebrou avançar e voltar 10s.
        scan = scan_code_de(virtual_key)
        try:
            self._key_event(virtual_key, scan, flags_de(virtual_key), 0)
            self._key_event(virtual_key, scan, flags_de(virtual_key, soltando=True), 0)
        except OSError:
            return False
        return True
