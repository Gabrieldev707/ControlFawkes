import ctypes
import struct
from unittest.mock import Mock, call

from app.input.keyboard import (
    KEYEVENTF_KEYUP,
    RELEASE_ONLY_VIRTUAL_KEYS,
    SAFE_KEY_VIRTUAL_KEYS,
    WindowsKeyboardAdapter,
    _Input,
    _InputUnion,
    _MouseInput,
)


def test_the_input_struct_has_the_size_send_input_validates():
    """O SendInput recusa a chamada inteira se `cbSize` não bater.

    A união precisa caber o maior membro (MOUSEINPUT), não só o KEYBDINPUT que
    usamos. Com a união menor, o INPUT ficava 32 bytes em vez de 40 e todo
    envio de texto voltava 0 com ERROR_INVALID_PARAMETER — o teclado remoto
    simplesmente não digitava, e nenhum mock pegava isso.
    """
    pointer_size = struct.calcsize("P")
    expected = 40 if pointer_size == 8 else 28

    assert ctypes.sizeof(_InputUnion) >= ctypes.sizeof(_MouseInput)
    assert ctypes.sizeof(_Input) == expected


def test_keyboard_adapter_writes_unicode_through_an_injected_writer():
    writer = Mock(return_value=True)
    adapter = WindowsKeyboardAdapter(unicode_writer=writer, key_event=Mock())

    assert adapter.write_text("Olá, Fawkes!") is True
    writer.assert_called_once_with("Olá, Fawkes!")


def test_keyboard_adapter_maps_every_safe_key_to_a_fixed_virtual_key():
    key_event = Mock()
    adapter = WindowsKeyboardAdapter(unicode_writer=Mock(return_value=True), key_event=key_event)

    for key, virtual_key in SAFE_KEY_VIRTUAL_KEYS.items():
        assert adapter.press_key(key) is True
        assert key_event.call_args_list[-2:] == [
            call(virtual_key, 0, 0, 0),
            call(virtual_key, 0, 2, 0),
        ]


def test_keyboard_adapter_reports_native_failures_without_false_success():
    adapter = WindowsKeyboardAdapter(
        unicode_writer=Mock(side_effect=OSError("unavailable")),
        key_event=Mock(side_effect=OSError("unavailable")),
    )

    assert adapter.write_text("texto") is False
    assert adapter.press_key("ENTER") is False


def test_release_all_only_emits_key_up_never_key_down():
    """Se emitisse keydown, o reset viraria uma forma de apertar Ctrl/Alt."""
    emitter = Mock()
    adapter = WindowsKeyboardAdapter(key_event=emitter)

    assert adapter.release_all() is True

    flags = {call.args[2] for call in emitter.call_args_list}
    assert flags == {KEYEVENTF_KEYUP}
    assert emitter.call_count == len(SAFE_KEY_VIRTUAL_KEYS) + len(RELEASE_ONLY_VIRTUAL_KEYS)


def test_release_all_covers_the_modifiers_that_cause_browser_zoom():
    emitter = Mock()
    adapter = WindowsKeyboardAdapter(key_event=emitter)

    adapter.release_all()

    released = {call.args[0] for call in emitter.call_args_list}
    for control_key in (0x11, 0xA2, 0xA3):  # CONTROL, LCONTROL, RCONTROL
        assert control_key in released


def test_a_failed_key_up_is_retried_so_the_key_does_not_stay_pressed():
    emitter = Mock(side_effect=[None, OSError("falha"), None])
    adapter = WindowsKeyboardAdapter(key_event=emitter)

    assert adapter.press_key("ARROW_DOWN") is False

    # keydown, keyup que falhou, keyup de recuperação.
    assert emitter.call_count == 3
    assert emitter.call_args_list[-1].args[2] == KEYEVENTF_KEYUP


def test_press_key_never_touches_a_modifier():
    """Nenhuma ação direcional pode carregar Ctrl, Alt ou Shift."""
    emitter = Mock()
    adapter = WindowsKeyboardAdapter(key_event=emitter)

    for key in SAFE_KEY_VIRTUAL_KEYS:
        adapter.press_key(key)

    used = {call.args[0] for call in emitter.call_args_list}
    assert not used & set(RELEASE_ONLY_VIRTUAL_KEYS)


def test_release_stuck_sends_nothing_when_nothing_is_stuck():
    """O caso normal, e o que mais importa.

    Isto roda a cada desconexão de WebSocket, e o celular desconecta o tempo
    todo: ao apagar a tela, ao trocar de app, a cada oscilação de rede. Mandar
    um keyup de Escape em cada uma tirava o navegador da tela cheia — o filme
    saía de tela cheia sozinho toda vez que o usuário guardava o celular.
    """
    emitter = Mock()
    adapter = WindowsKeyboardAdapter(key_event=emitter)
    adapter.press_key("ARROW_DOWN")
    emitter.reset_mock()

    assert adapter.release_stuck() is True
    emitter.assert_not_called()


def test_release_stuck_releases_a_key_whose_key_up_failed():
    # keydown ok, keyup falha, keyup de recuperação falha: aí sim ficou presa.
    emitter = Mock(side_effect=[None, OSError("falha"), OSError("falha")])
    adapter = WindowsKeyboardAdapter(key_event=emitter)
    adapter.press_key("ARROW_DOWN")

    emitter.side_effect = None
    emitter.reset_mock()

    assert adapter.release_stuck() is True
    assert emitter.call_args_list == [
        call(SAFE_KEY_VIRTUAL_KEYS["ARROW_DOWN"], 0, KEYEVENTF_KEYUP, 0),
    ]


def test_release_stuck_never_touches_escape_on_its_own():
    """Escape é o que derruba a tela cheia; ele só sai daqui se nós o
    tivermos apertado e deixado preso."""
    emitter = Mock()
    adapter = WindowsKeyboardAdapter(key_event=emitter)
    adapter.press_key("ARROW_UP")
    adapter.press_key("ENTER")
    emitter.reset_mock()

    adapter.release_stuck()

    used = {call.args[0] for call in emitter.call_args_list}
    assert SAFE_KEY_VIRTUAL_KEYS["ESCAPE"] not in used


def test_release_all_stays_available_for_the_explicit_reset():
    """A saída de emergência continua soltando tudo — inclusive Escape. É um
    comando que o usuário pede, não algo que acontece sozinho."""
    emitter = Mock()
    adapter = WindowsKeyboardAdapter(key_event=emitter)

    assert adapter.release_all() is True
    assert emitter.call_count == len(SAFE_KEY_VIRTUAL_KEYS) + len(RELEASE_ONLY_VIRTUAL_KEYS)
