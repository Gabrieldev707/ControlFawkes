import os
from typing import Mapping

from app.commands.parser import (
    PLATFORM_ALIASES,
    MediaControlIntent,
    NeedsPlatformIntent,
    OpenPlatformIntent,
    ParsedIntent,
    SearchMediaIntent,
    VolumeControlIntent,
    normalize_command,
)
from app.intelligence.context import DeviceContextStore
from app.intelligence.intents import to_parsed_intent
from app.intelligence.ollama import OllamaIntentResolver
from app.intelligence.resolver import LocalIntentResolver


class IntentFallbackService:
    def __init__(
        self,
        resolver: LocalIntentResolver,
        context_store: DeviceContextStore | None = None,
    ) -> None:
        self.resolver = resolver
        self.context_store = context_store or DeviceContextStore()

    async def resolve_unknown(self, device_id: str, text: str) -> ParsedIntent | None:
        context = self.context_store.get(device_id)
        try:
            local_intent = await self.resolver.resolve(text, context)
        except Exception:  # noqa: BLE001 - optional intelligence must not break controls
            return None
        if local_intent is None:
            return None
        try:
            parsed = to_parsed_intent(local_intent)
        except (TypeError, ValueError):
            return None
        if not self._is_grounded(parsed, text, context):
            return None
        return parsed

    def record(self, device_id: str, intent: ParsedIntent) -> None:
        if isinstance(intent, OpenPlatformIntent):
            self.context_store.update(
                device_id,
                platform=intent.platform,
                action=intent.type,
            )
        elif isinstance(intent, SearchMediaIntent):
            self.context_store.update(
                device_id,
                platform=intent.platform,
                query=intent.query,
                action=intent.type,
            )
        elif isinstance(intent, NeedsPlatformIntent):
            self.context_store.update(device_id, query=intent.query, action=intent.type)
        elif isinstance(intent, (MediaControlIntent, VolumeControlIntent)):
            self.context_store.update(device_id, action=intent.action)

    @staticmethod
    def _is_grounded(parsed: ParsedIntent, text: str, context) -> bool:
        normalized = normalize_command(text)
        if isinstance(parsed, (OpenPlatformIntent, SearchMediaIntent)):
            aliases = PLATFORM_ALIASES[parsed.platform]
            platform_is_explicit = any(
                f" {normalize_command(alias)} " in f" {normalized} "
                for alias in aliases
            )
            platform_is_contextual = context is not None and context.platform == parsed.platform
            if not (platform_is_explicit or platform_is_contextual):
                return False

        if isinstance(parsed, MediaControlIntent):
            grounding_terms = {
                "MEDIA_PLAY_PAUSE": ("play", "pausa", "continua", "toca"),
                "MEDIA_PREVIOUS": ("anterior",),
                "MEDIA_NEXT": ("proxima", "seguinte"),
                "MEDIA_SEEK_BACK": ("retrocede", "volta", "segundos"),
                "MEDIA_SEEK_FORWARD": ("avanca", "segundos"),
                "MEDIA_FULLSCREEN": ("tela cheia", "fullscreen"),
                "MEDIA_EXIT_FULLSCREEN": ("sair", "fecha", "fullscreen"),
            }
            return any(term in normalized for term in grounding_terms[parsed.action])

        if isinstance(parsed, VolumeControlIntent):
            return any(term in normalized for term in ("volume", "mudo", "mute", "som"))
        return True


def build_intent_service_from_env(
    environ: Mapping[str, str] | None = None,
) -> IntentFallbackService | None:
    values = os.environ if environ is None else environ
    mode = values.get("CONTROLFAWKES_LOCAL_AI", "auto").strip().lower()
    model = values.get("CONTROLFAWKES_OLLAMA_MODEL", "").strip()
    if mode not in {"auto", "on"} or not model:
        return None
    try:
        timeout = float(values.get("CONTROLFAWKES_OLLAMA_TIMEOUT", "5"))
        resolver = OllamaIntentResolver(
            values.get("CONTROLFAWKES_OLLAMA_URL", "http://127.0.0.1:11434"),
            model,
            timeout,
        )
    except (TypeError, ValueError):
        return None
    return IntentFallbackService(resolver)
