import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import sys
from typing import Literal, TypeAlias


NativeVolumeOperation: TypeAlias = Literal["GET", "SET", "DELTA", "TOGGLE_MUTE"]
NativeVolumeExecutor = Callable[[NativeVolumeOperation, int | None], tuple[int, bool]]


class WindowsVolumeError(RuntimeError):
    """Raised when the Windows Core Audio endpoint cannot confirm its state."""


@dataclass(frozen=True)
class VolumeState:
    level: int
    muted: bool


def _execute_core_audio(
    operation: NativeVolumeOperation,
    value: int | None,
) -> tuple[int, bool]:
    if sys.platform != "win32":
        raise WindowsVolumeError("Windows Core Audio is unavailable on this platform")

    try:
        import pythoncom
        from pycaw.pycaw import AudioUtilities
    except ImportError as error:
        raise WindowsVolumeError("Windows volume dependencies are unavailable") from error

    initialized = False
    try:
        pythoncom.CoInitialize()
        initialized = True
        endpoint = AudioUtilities.GetSpeakers().EndpointVolume

        if operation == "SET" and value is not None:
            endpoint.SetMasterVolumeLevelScalar(value / 100, None)
        elif operation == "DELTA" and value is not None:
            current = float(endpoint.GetMasterVolumeLevelScalar())
            next_level = max(0.0, min(1.0, current + (value / 100)))
            endpoint.SetMasterVolumeLevelScalar(next_level, None)
        elif operation == "TOGGLE_MUTE":
            endpoint.SetMute(int(not bool(endpoint.GetMute())), None)

        level = int(round(float(endpoint.GetMasterVolumeLevelScalar()) * 100))
        muted = bool(endpoint.GetMute())
        return max(0, min(100, level)), muted
    except WindowsVolumeError:
        raise
    except Exception as error:
        raise WindowsVolumeError("Windows Core Audio operation failed") from error
    finally:
        if initialized:
            pythoncom.CoUninitialize()


class WindowsVolumeAdapter:
    def __init__(self, executor: NativeVolumeExecutor | None = None) -> None:
        self._executor = executor or _execute_core_audio
        self._lock = asyncio.Lock()

    async def _execute(
        self,
        operation: NativeVolumeOperation,
        value: int | None = None,
    ) -> VolumeState:
        async with self._lock:
            try:
                level, muted = await asyncio.to_thread(self._executor, operation, value)
            except WindowsVolumeError:
                raise
            except Exception as error:
                raise WindowsVolumeError("Windows Core Audio operation failed") from error
        return VolumeState(level=max(0, min(100, int(level))), muted=bool(muted))

    async def get_state(self) -> VolumeState:
        return await self._execute("GET")

    async def set_level(self, level: int) -> VolumeState:
        return await self._execute("SET", level)

    async def change_level(self, delta: int) -> VolumeState:
        return await self._execute("DELTA", delta)

    async def toggle_mute(self) -> VolumeState:
        return await self._execute("TOGGLE_MUTE")
