from collections import defaultdict, deque
from collections.abc import Callable, Hashable
import ctypes
import sys
import time


MouseEvent = Callable[[int, int, int, int, int], None]

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800


class WindowsPointerAdapter:
    def __init__(self, mouse_event: MouseEvent | None = None) -> None:
        if mouse_event is not None:
            self._mouse_event: MouseEvent | None = mouse_event
        elif sys.platform == "win32":
            self._mouse_event = ctypes.windll.user32.mouse_event
        else:
            self._mouse_event = None

    def _emit(self, *events: tuple[int, int, int, int, int]) -> bool:
        if self._mouse_event is None:
            return False
        try:
            for event in events:
                self._mouse_event(*event)
        except OSError:
            return False
        return True

    def move(self, dx: float, dy: float) -> bool:
        return self._emit((MOUSEEVENTF_MOVE, round(dx), round(dy), 0, 0))

    def click(self) -> bool:
        return self._emit(
            (MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0),
            (MOUSEEVENTF_LEFTUP, 0, 0, 0, 0),
        )

    def double_click(self) -> bool:
        return self._emit(
            (MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0),
            (MOUSEEVENTF_LEFTUP, 0, 0, 0, 0),
            (MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0),
            (MOUSEEVENTF_LEFTUP, 0, 0, 0, 0),
        )

    def right_click(self) -> bool:
        return self._emit(
            (MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0),
            (MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0),
        )

    def scroll(self, delta: int) -> bool:
        return self._emit((MOUSEEVENTF_WHEEL, 0, 0, delta, 0))

    def pointer_down(self) -> bool:
        return self._emit((MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0))

    def pointer_up(self) -> bool:
        return self._emit((MOUSEEVENTF_LEFTUP, 0, 0, 0, 0))


class PointerRateLimiter:
    def __init__(
        self,
        max_updates: int = 60,
        window_seconds: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_updates = max_updates
        self.window_seconds = window_seconds
        self._clock = clock
        self._updates: dict[Hashable, deque[float]] = defaultdict(deque)

    def allow(self, key: Hashable) -> bool:
        now = self._clock()
        cutoff = now - self.window_seconds
        updates = self._updates[key]
        while updates and updates[0] <= cutoff:
            updates.popleft()
        if len(updates) >= self.max_updates:
            return False
        updates.append(now)
        return True

    def clear(self, key: Hashable) -> None:
        self._updates.pop(key, None)
