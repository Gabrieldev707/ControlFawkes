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


# MOUSEINPUT e HARDWAREINPUT não são usados aqui, mas precisam existir na união.
# O SendInput valida `cbSize` contra o INPUT completo do Windows, e quem manda
# no tamanho é o maior membro — MOUSEINPUT, com 32 bytes no x64. Com uma união
# só de KEYBDINPUT o INPUT fica 32 bytes em vez de 40, e toda chamada volta 0
# com ERROR_INVALID_PARAMETER: nenhum texto era digitado.
class _MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.WPARAM),
    ]


class _HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _InputUnion(ctypes.Union):
    _fields_ = [("mi", _MouseInput), ("ki", _KeyboardInput), ("hi", _HardwareInput)]


class _Input(ctypes.Structure):
    _anonymous_ = ("data",)
    _fields_ = [("type", wintypes.DWORD), ("data", _InputUnion)]


def _send_input_function():
    """SendInput com assinatura declarada.

    Sem argtypes, o ctypes trunca o ponteiro do array em 32 bits e a chamada
    falha de forma silenciosa em processos de 64 bits.
    """
    function = ctypes.windll.user32.SendInput
    function.argtypes = (wintypes.UINT, ctypes.POINTER(_Input), ctypes.c_int)
    function.restype = wintypes.UINT
    return function


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
    sent = _send_input_function()(len(inputs), input_array, ctypes.sizeof(_Input))
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
        # Teclas que este adapter apertou e não conseguiu soltar. Normalmente
        # vazio: `press_key` solta a sua no mesmo comando.
        self._stuck: set[int] = set()

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
            self._stuck.add(virtual_key)
            self._key_event(virtual_key, 0, KEYEVENTF_KEYUP, 0)
            self._stuck.discard(virtual_key)
        except OSError:
            # Se o keydown passou e o keyup falhou, a tecla fica presa no
            # Windows. Uma seta presa repete sozinha; um Enter preso reabre
            # itens sem parar. O keyup precisa ser tentado de novo.
            if pressed:
                try:
                    self._key_event(virtual_key, 0, KEYEVENTF_KEYUP, 0)
                    self._stuck.discard(virtual_key)
                except OSError:
                    pass
            return False
        return True

    def release_stuck(self) -> bool:
        """Solta só o que este adapter deixou preso. Quase sempre não faz nada.

        Existe por causa de um efeito colateral caro: o `release_all` roda a
        cada desconexão de WebSocket, e o celular desconecta o tempo todo — ao
        apagar a tela, ao trocar de app, a cada oscilação de rede. Cada uma
        dessas mandava um keyup de Escape para a janela em foco, e o Escape
        tira o navegador da tela cheia da Fullscreen API. Na prática: o filme
        saía de tela cheia sozinho toda vez que o usuário guardava o celular.

        Como `press_key` já solta a própria tecla no mesmo comando, o conjunto
        normalmente está vazio e nenhum evento é enviado.
        """
        if self._key_event is None:
            return False

        released = True
        for virtual_key in tuple(self._stuck):
            try:
                self._key_event(virtual_key, 0, KEYEVENTF_KEYUP, 0)
                self._stuck.discard(virtual_key)
            except OSError:
                released = False
        return released

    def release_all(self) -> bool:
        """Solta todas as teclas conhecidas. Só emite keyup, nunca keydown.

        A saída de emergência, para quando algo travou fora do que sabemos ter
        apertado — um Ctrl preso por outro programa, por exemplo. Fica reservada
        ao comando explícito de reset: como manda Escape junto, usá-la de forma
        automática derrubaria a tela cheia de quem está assistindo.
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
                self._stuck.discard(virtual_key)
            except OSError:
                released = False
        return released
