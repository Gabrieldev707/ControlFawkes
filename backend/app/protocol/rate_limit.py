import time
from collections import deque
from typing import Dict

class RateLimiter:
    def __init__(self, max_ops: int, time_window: float = 1.0):
        self.max_ops = max_ops
        self.time_window = time_window
        # map connection_id -> deque of timestamps
        self._history: Dict[str, deque] = {}

    def check_and_consume(self, connection_id: str) -> bool:
        """Returns True if allowed, False if rate limited."""
        now = time.time()
        
        if connection_id not in self._history:
            self._history[connection_id] = deque()
            
        history = self._history[connection_id]
        
        # Remove old timestamps
        while history and history[0] < now - self.time_window:
            history.popleft()
            
        if len(history) >= self.max_ops:
            return False
            
        history.append(now)
        return True

    def remove_connection(self, connection_id: str):
        if connection_id in self._history:
            del self._history[connection_id]
