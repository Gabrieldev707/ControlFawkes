from unittest.mock import AsyncMock

import pytest

from app.commands.parser import SearchMediaIntent
from app.intelligence.context import DeviceContextStore
from app.intelligence.intents import LocalSearchMediaIntent, LocalUnknownIntent
from app.intelligence.service import IntentFallbackService, build_intent_service_from_env


@pytest.mark.asyncio
async def test_service_passes_only_same_device_context_and_converts_result():
    resolver = AsyncMock()
    resolver.resolve.return_value = LocalSearchMediaIntent(
        intent="SEARCH_MEDIA",
        platform="YOUTUBE",
        query="HUMBLE",
    )
    contexts = DeviceContextStore()
    contexts.update("device-a", platform="YOUTUBE", query="Kendrick")
    contexts.update("device-b", platform="SPOTIFY", query="Runaway")
    service = IntentFallbackService(resolver, contexts)

    result = await service.resolve_unknown("device-a", "coloca aquela")

    assert result == SearchMediaIntent(type="SEARCH_MEDIA", platform="YOUTUBE", query="HUMBLE")
    passed_context = resolver.resolve.await_args.args[1]
    assert passed_context.query == "Kendrick"
    assert passed_context.query != "Runaway"


@pytest.mark.asyncio
async def test_service_returns_none_when_resolver_is_offline_or_invalid():
    resolver = AsyncMock()
    resolver.resolve.return_value = None
    service = IntentFallbackService(resolver)

    assert await service.resolve_unknown("device-a", "não reconhecido") is None
    resolver.resolve.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_contains_an_unexpected_resolver_exception():
    resolver = AsyncMock()
    resolver.resolve.side_effect = RuntimeError("local runtime failed")
    service = IntentFallbackService(resolver)

    assert await service.resolve_unknown("device-a", "não reconhecido") is None


@pytest.mark.asyncio
async def test_service_treats_model_abstention_as_the_safe_fallback():
    resolver = AsyncMock()
    resolver.resolve.return_value = LocalUnknownIntent(intent="UNKNOWN")
    service = IntentFallbackService(resolver)

    assert await service.resolve_unknown("device-a", "ambíguo") is None


@pytest.mark.asyncio
async def test_service_rejects_an_ungrounded_platform_even_when_schema_is_valid():
    resolver = AsyncMock()
    resolver.resolve.return_value = LocalSearchMediaIntent(
        intent="SEARCH_MEDIA",
        platform="YOUTUBE",
        query="Kendrick",
    )
    service = IntentFallbackService(resolver)

    assert await service.resolve_unknown("device-a", "coloca aquela música") is None


def test_record_keeps_only_bounded_context_fields():
    resolver = AsyncMock()
    service = IntentFallbackService(resolver)
    intent = SearchMediaIntent(type="SEARCH_MEDIA", platform="SPOTIFY", query="Runaway")

    service.record("device-a", intent)

    context = service.context_store.get("device-a")
    assert context.platform == "SPOTIFY"
    assert context.query == "Runaway"
    assert context.action == "SEARCH_MEDIA"


def test_environment_configuration_is_optional_and_fail_closed():
    assert build_intent_service_from_env({"CONTROLFAWKES_LOCAL_AI": "off"}) is None
    assert build_intent_service_from_env({"CONTROLFAWKES_LOCAL_AI": "auto"}) is None
    assert build_intent_service_from_env({
        "CONTROLFAWKES_LOCAL_AI": "on",
        "CONTROLFAWKES_OLLAMA_MODEL": "qwen2.5:3b",
        "CONTROLFAWKES_OLLAMA_URL": "http://remote-host:11434",
    }) is None

    service = build_intent_service_from_env({
        "CONTROLFAWKES_LOCAL_AI": "auto",
        "CONTROLFAWKES_OLLAMA_MODEL": "qwen2.5:3b",
    })
    assert service is not None
