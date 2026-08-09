from typing import Protocol

from app.intelligence.context import DeviceContext
from app.intelligence.intents import LocalIntent


class LocalIntentResolver(Protocol):
    async def resolve(
        self,
        text: str,
        context: DeviceContext | None,
    ) -> LocalIntent | None:
        """Interpret unknown text without executing any action."""
