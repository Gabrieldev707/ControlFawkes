from collections import OrderedDict
from dataclasses import dataclass
import time
from typing import Callable

from app.schemas.ws import Platform


@dataclass(frozen=True)
class DeviceContext:
    platform: Platform | None
    query: str | None
    action: str | None
    updated_at: float


class DeviceContextStore:
    """Small volatile LRU store keyed by the authenticated device ID."""

    def __init__(
        self,
        ttl_seconds: float = 600,
        max_devices: int = 32,
        time_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0 or max_devices <= 0:
            raise ValueError("Context bounds must be positive.")
        self.ttl_seconds = ttl_seconds
        self.max_devices = max_devices
        self._time = time_fn
        self._contexts: OrderedDict[str, DeviceContext] = OrderedDict()

    def get(self, device_id: str) -> DeviceContext | None:
        self._purge_expired()
        context = self._contexts.get(device_id)
        if context is not None:
            self._contexts.move_to_end(device_id)
        return context

    def update(
        self,
        device_id: str,
        *,
        platform: Platform | None = None,
        query: str | None = None,
        action: str | None = None,
    ) -> DeviceContext:
        self._validate_field("device_id", device_id, 128)
        if query is not None:
            self._validate_field("query", query, 200)
        if action is not None:
            self._validate_field("action", action, 64)

        self._purge_expired()
        previous = self._contexts.get(device_id)
        context = DeviceContext(
            platform=platform if platform is not None else (previous.platform if previous else None),
            query=query if query is not None else (previous.query if previous else None),
            action=action if action is not None else (previous.action if previous else None),
            updated_at=self._time(),
        )
        self._contexts[device_id] = context
        self._contexts.move_to_end(device_id)
        while len(self._contexts) > self.max_devices:
            self._contexts.popitem(last=False)
        return context

    def clear(self, device_id: str) -> None:
        self._contexts.pop(device_id, None)

    def _purge_expired(self) -> None:
        now = self._time()
        expired = [
            device_id
            for device_id, context in self._contexts.items()
            if now - context.updated_at >= self.ttl_seconds
        ]
        for device_id in expired:
            self._contexts.pop(device_id, None)

    @staticmethod
    def _validate_field(name: str, value: str, limit: int) -> None:
        if not value or len(value) > limit:
            raise ValueError(f"{name} must contain 1 to {limit} characters.")
