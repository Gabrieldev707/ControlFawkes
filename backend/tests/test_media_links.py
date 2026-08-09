import pytest

from app.commands.parser import OpenMediaLinkIntent, UnknownIntent, parse_command
from app.platforms.links import parse_media_link
from app.platforms.registry import is_browser_url_allowed


VIDEO = "dQw4w9WgXcQ"


@pytest.mark.parametrize("url", [
    f"https://www.youtube.com/watch?v={VIDEO}",
    f"https://youtube.com/watch?v={VIDEO}",
    f"https://m.youtube.com/watch?v={VIDEO}",
    f"https://music.youtube.com/watch?v={VIDEO}",
    f"https://youtu.be/{VIDEO}",
])
def test_allowed_links_are_canonicalized_to_a_single_form(url):
    link = parse_media_link(url)

    assert link is not None
    assert link.platform == "YOUTUBE"
    assert link.video_id == VIDEO
    # A URL é reconstruída a partir do id validado, não repassada.
    assert link.url == f"https://www.youtube.com/watch?v={VIDEO}"
    assert is_browser_url_allowed(link.url) is True


def test_the_start_time_is_preserved_when_it_is_well_formed():
    link = parse_media_link(f"https://youtu.be/{VIDEO}?t=42s")

    assert link is not None
    assert link.url == f"https://www.youtube.com/watch?v={VIDEO}&t=42s"
    assert is_browser_url_allowed(link.url) is True


@pytest.mark.parametrize("url", [
    # Esquemas perigosos.
    f"javascript:window.open('https://www.youtube.com/watch?v={VIDEO}')",
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "file:///C:/Windows/System32/cmd.exe",
    f"http://www.youtube.com/watch?v={VIDEO}",
    f"ftp://www.youtube.com/watch?v={VIDEO}",
    # Hostnames enganosos: sufixo, prefixo e homógrafo simples.
    f"https://www.youtube.com.evil.example/watch?v={VIDEO}",
    f"https://youtube.com.evil.example/watch?v={VIDEO}",
    f"https://evilyoutube.com/watch?v={VIDEO}",
    f"https://youtu.be.evil.example/{VIDEO}",
    f"https://evil.example/watch?v={VIDEO}",
    # Credenciais e porta.
    f"https://user:senha@www.youtube.com/watch?v={VIDEO}",
    f"https://www.youtube.com:8443/watch?v={VIDEO}",
    # Path fora do previsto.
    f"https://www.youtube.com/redirect?q=evil&v={VIDEO}",
    "https://www.youtube.com/watch/../../admin",
    "https://youtu.be/../evil",
    # Id inválido.
    "https://www.youtube.com/watch?v=",
    "https://www.youtube.com/watch?v=curto",
    "https://www.youtube.com/watch?v=id_com_mais_de_onze",
    "https://youtu.be/",
    # Parâmetro extra não previsto.
    f"https://www.youtube.com/watch?v={VIDEO}&redirect=https://evil.example",
    f"https://www.youtube.com/watch?v={VIDEO}&list=PLevil",
    # Ruído e injeção.
    "",
    "   ",
    f"https://www.youtube.com/watch?v={VIDEO} && shutdown /s",
    f"abre https://www.youtube.com/watch?v={VIDEO} e desliga o computador",
])
def test_unsafe_or_unknown_links_are_rejected(url):
    assert parse_media_link(url) is None


@pytest.mark.parametrize("url", [
    f"https://www.youtube.com/watch?v={VIDEO}",
    f"https://youtu.be/{VIDEO}",
])
def test_the_parser_turns_an_allowed_link_into_an_open_link_intent(url):
    result = parse_command(url)

    assert isinstance(result, OpenMediaLinkIntent)
    assert result.platform == "YOUTUBE"
    assert result.url == f"https://www.youtube.com/watch?v={VIDEO}"


@pytest.mark.parametrize("text", [
    f"https://evil.example/watch?v={VIDEO}",
    "abre https://example.com",
    f"https://www.youtube.com/watch?v={VIDEO}&list=PLevil",
])
def test_a_link_that_fails_validation_never_becomes_a_command(text):
    assert isinstance(parse_command(text), UnknownIntent)


def test_a_rejected_link_is_also_refused_by_the_launcher_allowlist():
    """Segunda camada: mesmo que algo escape do parser, o launcher recusa."""
    assert is_browser_url_allowed(f"https://www.youtube.com.evil.example/watch?v={VIDEO}") is False
    assert is_browser_url_allowed("https://www.youtube.com/watch?v=arbitrario") is False
    assert is_browser_url_allowed(f"https://www.youtube.com/watch?v={VIDEO}&list=PLevil") is False
