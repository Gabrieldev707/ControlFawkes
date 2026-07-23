from unittest.mock import Mock, call

from app.input.pointer import PointerRateLimiter, WindowsPointerAdapter


def test_pointer_adapter_maps_only_fixed_actions_to_windows_events():
    mouse_event = Mock()
    adapter = WindowsPointerAdapter(mouse_event=mouse_event)

    assert adapter.move(12.4, -7.6) is True
    assert adapter.click() is True
    assert adapter.double_click() is True
    assert adapter.right_click() is True
    assert adapter.scroll(-120) is True
    assert adapter.pointer_down() is True
    assert adapter.pointer_up() is True

    assert mouse_event.call_args_list == [
        call(0x0001, 12, -8, 0, 0),
        call(0x0002, 0, 0, 0, 0), call(0x0004, 0, 0, 0, 0),
        call(0x0002, 0, 0, 0, 0), call(0x0004, 0, 0, 0, 0),
        call(0x0002, 0, 0, 0, 0), call(0x0004, 0, 0, 0, 0),
        call(0x0008, 0, 0, 0, 0), call(0x0010, 0, 0, 0, 0),
        call(0x0800, 0, 0, -120, 0),
        call(0x0002, 0, 0, 0, 0),
        call(0x0004, 0, 0, 0, 0),
    ]


def test_pointer_adapter_reports_native_failure_without_false_success():
    adapter = WindowsPointerAdapter(mouse_event=Mock(side_effect=OSError("unavailable")))

    assert adapter.click() is False


def test_pointer_rate_limiter_is_scoped_and_uses_a_monotonic_window():
    clock = Mock(return_value=10.0)
    limiter = PointerRateLimiter(max_updates=2, window_seconds=1.0, clock=clock)

    assert limiter.allow("device-a") is True
    assert limiter.allow("device-a") is True
    assert limiter.allow("device-a") is False
    assert limiter.allow("device-b") is True

    clock.return_value = 11.01
    assert limiter.allow("device-a") is True
    limiter.clear("device-a")
    assert limiter.allow("device-a") is True
