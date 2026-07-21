from unittest.mock import Mock

import pytest

from app.windows.volume import VolumeState, WindowsVolumeAdapter, WindowsVolumeError


@pytest.mark.asyncio
async def test_volume_adapter_returns_the_state_re_read_by_core_audio():
    executor = Mock(return_value=(57, True))
    adapter = WindowsVolumeAdapter(executor=executor)

    state = await adapter.set_level(73)

    assert state == VolumeState(level=57, muted=True)
    executor.assert_called_once_with("SET", 73)


@pytest.mark.asyncio
async def test_volume_adapter_uses_only_fixed_operations():
    executor = Mock(side_effect=[(41, False), (46, False), (46, True)])
    adapter = WindowsVolumeAdapter(executor=executor)

    assert await adapter.get_state() == VolumeState(level=41, muted=False)
    assert await adapter.change_level(5) == VolumeState(level=46, muted=False)
    assert await adapter.toggle_mute() == VolumeState(level=46, muted=True)
    assert [entry.args for entry in executor.call_args_list] == [
        ("GET", None),
        ("DELTA", 5),
        ("TOGGLE_MUTE", None),
    ]


@pytest.mark.asyncio
async def test_volume_adapter_wraps_native_failures_without_false_success():
    adapter = WindowsVolumeAdapter(executor=Mock(side_effect=OSError("Core Audio failed")))

    with pytest.raises(WindowsVolumeError):
        await adapter.get_state()
