import sys
import asyncio
from typing import Tuple

class WindowsAPIUnavailable(Exception):
    pass

class CoreAudioFailed(Exception):
    pass

class WindowsVolumeService:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._is_windows = sys.platform == 'win32'
        
    def _execute_in_com_thread(self, action: str, level: float = None, delta: float = None) -> Tuple[int, bool]:
        """
        Internal synchronous method that runs in a dedicated thread.
        Isolates COM initialization and pycaw logic.
        action: 'GET', 'SET', 'STEP', 'TOGGLE_MUTE'
        Returns: (level_int_0_to_100, is_muted)
        """
        if not self._is_windows:
            raise WindowsAPIUnavailable("Not running on Windows.")

        import pythoncom
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL

        pythoncom.CoInitialize()
        try:
            devices = AudioUtilities.GetSpeakers()
            volume = devices.EndpointVolume
            
            if action == 'SET' and level is not None:
                volume.SetMasterVolumeLevelScalar(level, None)
            elif action == 'STEP' and delta is not None:
                current = volume.GetMasterVolumeLevelScalar()
                new_level = max(0.0, min(1.0, current + delta))
                volume.SetMasterVolumeLevelScalar(new_level, None)
            elif action == 'TOGGLE_MUTE':
                muted = volume.GetMute()
                volume.SetMute(int(not muted), None)
            
            # Always re-read actual state
            final_scalar = volume.GetMasterVolumeLevelScalar()
            final_muted = bool(volume.GetMute())
            
            # Convert 0.0-1.0 to 0-100 integer
            final_level_int = int(round(final_scalar * 100))
            return final_level_int, final_muted

        except Exception as e:
            raise CoreAudioFailed(f"Core Audio Failed: {e}")
        finally:
            pythoncom.CoUninitialize()

    async def get_state(self) -> Tuple[int, bool]:
        async with self._lock:
            return await asyncio.to_thread(self._execute_in_com_thread, 'GET')

    async def set_level(self, level_0_to_100: int) -> Tuple[int, bool]:
        async with self._lock:
            level_scalar = max(0.0, min(1.0, level_0_to_100 / 100.0))
            return await asyncio.to_thread(self._execute_in_com_thread, 'SET', level=level_scalar)

    async def step(self, delta_0_to_100: int) -> Tuple[int, bool]:
        async with self._lock:
            delta_scalar = delta_0_to_100 / 100.0
            return await asyncio.to_thread(self._execute_in_com_thread, 'STEP', delta=delta_scalar)

    async def toggle_mute(self) -> Tuple[int, bool]:
        async with self._lock:
            return await asyncio.to_thread(self._execute_in_com_thread, 'TOGGLE_MUTE')
