from unittest.mock import Mock, call

from app.input.keyboard import (
    KEYEVENTF_KEYUP,
    RELEASE_ONLY_VIRTUAL_KEYS,
    SAFE_KEY_VIRTUAL_KEYS,
    WindowsKeyboardAdapter,
)


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
