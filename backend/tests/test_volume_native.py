import pytest
import sys
import asyncio
from app.windows.volume import WindowsVolumeService

@pytest.mark.asyncio
async def test_native_volume_get_state():
    if sys.platform != 'win32':
        pytest.skip("Smoke test nativo requires Windows")
    
    service = WindowsVolumeService()
    try:
        level, muted = await service.get_state()
        assert isinstance(level, int)
        assert 0 <= level <= 100
        assert isinstance(muted, bool)
    except Exception as e:
        pytest.fail(f"Native volume read failed: {e}")
