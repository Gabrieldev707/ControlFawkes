from unittest.mock import Mock

import pytest

from app.media.session import MediaSession, WindowsMediaSessionDetector
from app.media.windows_adapter import WindowsMediaAdapter


@pytest.mark.parametrize(
    ("title", "platform", "kind"),
    [
        ("Runaway • Kanye West - YouTube - Google Chrome", "YOUTUBE", "WEB"),
        ("Interestelar - Netflix - Google Chrome", "NETFLIX", "WEB"),
        ("The Last of Us - Max - Google Chrome", "MAX", "WEB"),
        ("Prime Video - Google Chrome", "PRIME_VIDEO", "WEB"),
        ("Disney+ - Google Chrome", "DISNEY_PLUS", "WEB"),
        ("Kendrick Lamar - Spotify", "SPOTIFY", "APP"),
        ("Spotify - Google Chrome", "SPOTIFY", "WEB"),
    ],
)
def test_media_session_detector_identifies_only_known_foreground_players(
    title,
    platform,
    kind,
):
    detector = WindowsMediaSessionDetector(foreground_title_reader=lambda: title)

    assert detector.detect() == MediaSession(platform=platform, kind=kind)


@pytest.mark.parametrize("title", [None, "", "Documentos - Google Chrome", "Bloco de Notas"])
def test_media_session_detector_rejects_unknown_or_missing_foreground_window(title):
    detector = WindowsMediaSessionDetector(foreground_title_reader=lambda: title)

    assert detector.detect() is None


@pytest.mark.parametrize(
    ("platform", "action", "virtual_key"),
    [
        ("YOUTUBE", "MEDIA_PLAY_PAUSE", 0xB3),
        ("YOUTUBE", "MEDIA_SEEK_BACK", 0x4A),
        ("YOUTUBE", "MEDIA_SEEK_FORWARD", 0x4C),
        ("YOUTUBE", "MEDIA_FULLSCREEN", 0x46),
        ("YOUTUBE", "MEDIA_EXIT_FULLSCREEN", 0x1B),
        ("SPOTIFY", "MEDIA_PREVIOUS", 0xB1),
        ("SPOTIFY", "MEDIA_NEXT", 0xB0),
        ("NETFLIX", "MEDIA_SEEK_BACK", 0x25),
        ("MAX", "MEDIA_SEEK_FORWARD", 0x27),
    ],
)
def test_media_adapter_uses_platform_specific_fixed_keys(platform, action, virtual_key):
    emitter = Mock()
    adapter = WindowsMediaAdapter(emitter)

    assert adapter.supports(action, platform) is True
    assert adapter.execute(action, platform) is True
    assert [call.args[0] for call in emitter.call_args_list] == [virtual_key, virtual_key]


@pytest.mark.parametrize(
    ("platform", "action"),
    [
        ("SPOTIFY", "MEDIA_SEEK_BACK"),
        ("SPOTIFY", "MEDIA_FULLSCREEN"),
        ("NETFLIX", "MEDIA_PREVIOUS"),
        ("DISNEY_PLUS", "MEDIA_NEXT"),
    ],
)
def test_media_adapter_rejects_unsupported_platform_action_without_key_event(
    platform,
    action,
):
    emitter = Mock()
    adapter = WindowsMediaAdapter(emitter)

    assert adapter.supports(action, platform) is False
    assert adapter.execute(action, platform) is False
    emitter.assert_not_called()
