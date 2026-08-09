from collections.abc import Callable
import ctypes
from ctypes import wintypes
import sys
from typing import Literal, TypeAlias


SafeKey: TypeAlias = Literal[
    "ENTER",
    "BACKSPACE",
    "ESCAPE",
    "ARROW_UP",
    "ARROW_DOWN",
    "ARROW_LEFT",
    "ARROW_RIGHT",
    "TAB",
    "SPACE",
]

SAFE_KEY_VIRTUAL_KEYS: dict[SafeKey, int] = {
    "ENTER": 0x0D,
    "BACKSPACE": 0x08,
    "ESCAPE": 0x1B,
    "ARROW_UP": 0x26,
    "ARROW_DOWN": 0x28,
    "ARROW_LEFT": 0x25,
    "ARROW_RIGHT": 0x27,
    "TAB": 0x09,
    "SPACE": 0x20,
}

# Teclas liberadas pelo reset defensivo. Inclui os modificadores de propósito:
# um Ctrl preso é exatamente o que provoca zoom do navegador ao rolar, e a única
# forma de destravá-lo é mandar o keyup dele.
#
# Só é seguro porque o reset emite **apenas keyup**, nunca keydown: soltar uma
# tecla que não está pressionada não tem efeito, então esta lista não amplia o
# que o ControlFawkes consegue apertar.
RELEASE_ONLY_VIRTUAL_KEYS: tuple[int, ...] = (
    0x11,  # CONTROL
    0xA2,  # LCONTROL
    0xA3,  # RCONTROL
    0x12,  # MENU (Alt)
    0xA4,  # LMENU
    0xA5,  # RMENU
    0x10,  # SHIFT
    0xA0,  # LSHIFT
    0xA1,  # RSHIFT
    0x5B,  # LWIN
    0x5C,  # RWIN
)

UnicodeWriter = Callable[[str], bool]
KeyEvent = Callable[[int, int, int, int], None]
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1


class _KeyboardInput(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.WPARAM),
    ]


class _InputUnion(ctypes.Union):
    _fields_ = [("ki", _KeyboardInput)]


class _Input(ctypes.Structure):
    _anonymous_ = ("data",)
    _fields_ = [("type", wintypes.DWORD), ("data", _InputUnion)]


def _write_unicode_with_send_input(text: str) -> bool:
    if sys.platform != "win32":
        return False

    encoded = text.encode("utf-16-le")
    units = [int.from_bytes(encoded[index:index + 2], "little") for index in range(0, len(encoded), 2)]
    inputs: list[_Input] = []
    for unit in units:
        inputs.extend([
            _Input(
                type=INPUT_KEYBOARD,
                data=_InputUnion(ki=_KeyboardInput(0, unit, KEYEVENTF_UNICODE, 0, 0)),
            ),
            _Input(
                type=INPUT_KEYBOARD,
                data=_InputUnion(
                    ki=_KeyboardInput(0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0),
                ),
            ),
        ])
    if not inputs:
        return False
    input_array = (_Input * len(inputs))(*inputs)
    sent = ctypes.windll.user32.SendInput(len(inputs), input_array, ctypes.sizeof(_Input))
    return sent == len(inputs)


class WindowsKeyboardAdapter:
    def __init__(
        self,
        unicode_writer: UnicodeWriter | None = None,
        key_event: KeyEvent | None = None,
    ) -> None:
        self._unicode_writer = unicode_writer or _write_unicode_with_send_input
        if key_event is not None:
            self._key_event: KeyEvent | None = key_event
        elif sys.platform == "win32":
            self._key_event = ctypes.windll.user32.keybd_event
        else:
            self._key_event = None

    def write_text(self, text: str) -> bool:
        try:
            return bool(self._unicode_writer(text))
        except OSError:
            return False

    def press_key(self, key: SafeKey) -> bool:
        if self._key_event is None:
            return False
        virtual_key = SAFE_KEY_VIRTUAL_KEYS[key]
        pressed = False
        try:
            self._key_event(virtual_key, 0, 0, 0)
            pressed = True
            self._key_event(virtual_key, 0, KEYEVENTF_KEYUP, 0)
        except OSError:
            # Se o keydown passou e o keyup falhou, a tecla fica presa no
            # Windows. Uma seta presa repete sozinha; um Enter preso reabre
            # itens sem parar. O keyup precisa ser tentado de novo.
            if pressed:
                try:
                    self._key_event(virtual_key, 0, KEYEVENTF_KEYUP, 0)
                except OSError:
                    pass
            return False
        return True

    def release_all(self) -> bool:
        """Solta as teclas conhecidas. Só emite keyup, nunca keydown.

        Serve para destravar uma tecla presa por falha ou por desconexão no
        meio de um comando.
        """
        if self._key_event is None:
            return False

        released = True
        virtual_keys = (
            *SAFE_KEY_VIRTUAL_KEYS.values(),
            *RELEASE_ONLY_VIRTUAL_KEYS,
        )
        for virtual_key in virtual_keys:
            try:
                self._key_event(virtual_key, 0, KEYEVENTF_KEYUP, 0)
            except OSError:
                released = False
        return released
