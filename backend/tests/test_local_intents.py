import pytest
from pydantic import ValidationError

from app.commands.parser import (
    MediaControlIntent,
    OpenPlatformIntent,
    SearchMediaIntent,
    VolumeControlIntent,
)
from app.intelligence.intents import parse_local_intent, to_parsed_intent


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"intent": "OPEN_PLATFORM", "platform": "NETFLIX"}, OpenPlatformIntent(type="OPEN_PLATFORM", platform="NETFLIX")),
        (
            {"intent": "SEARCH_MEDIA", "platform": "YOUTUBE", "query": "Kendrick HUMBLE"},
            SearchMediaIntent(type="SEARCH_MEDIA", platform="YOUTUBE", query="Kendrick HUMBLE"),
        ),
        (
            {"intent": "MEDIA_CONTROL", "action": "MEDIA_NEXT"},
            MediaControlIntent(action="MEDIA_NEXT"),
        ),
        (
            {"intent": "SYSTEM_VOLUME", "action": "SYSTEM_VOLUME_DELTA", "delta": 5},
            VolumeControlIntent(action="SYSTEM_VOLUME_DELTA", delta=5),
        ),
    ],
)
def test_valid_local_results_convert_only_to_existing_intents(payload, expected):
    assert to_parsed_intent(parse_local_intent(payload)) == expected


@pytest.mark.parametrize(
    "payload",
    [
        {"intent": "EXECUTE_POWERSHELL", "command": "shutdown"},
        {"intent": "OPEN_PLATFORM", "platform": "PIRATE_STREAM"},
        {"intent": "OPEN_PLATFORM", "platform": "YOUTUBE", "url": "https://evil.test"},
        {"intent": "MEDIA_CONTROL", "action": "MEDIA_DELETE_FILES"},
        {"intent": "SYSTEM_VOLUME", "action": "SYSTEM_VOLUME_SET", "level": 101},
        {"intent": "SYSTEM_VOLUME", "action": "SYSTEM_VOLUME_SET", "level": "42"},
        {"intent": "SYSTEM_VOLUME", "action": "SYSTEM_VOLUME_DELTA", "delta": 10},
        {"intent": "SEARCH_MEDIA", "platform": "MAX", "query": "Interestelar"},
        {"intent": "SEARCH_MEDIA", "platform": "YOUTUBE", "query": "javascript:alert(1)"},
        {"intent": "SEARCH_MEDIA", "platform": "YOUTUBE", "query": "q" * 201},
    ],
)
def test_local_results_reject_hallucination_coercion_extra_fields_and_unsafe_queries(payload):
    with pytest.raises((ValidationError, ValueError)):
        to_parsed_intent(parse_local_intent(payload))
