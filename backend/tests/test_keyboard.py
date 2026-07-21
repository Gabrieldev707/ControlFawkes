from unittest.mock import Mock, call

from app.input.keyboard import SAFE_KEY_VIRTUAL_KEYS, WindowsKeyboardAdapter


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
