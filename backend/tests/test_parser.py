import pytest

from app.commands.parser import (
    NeedsPlatformIntent,
    OpenPlatformIntent,
    SearchMediaIntent,
    ShowHelpIntent,
    UnknownIntent,
    normalize_command,
    parse_command,
)


@pytest.mark.parametrize(
    ("command", "platform"),
    [
        ("abre netflix", "NETFLIX"),
        ("abrir netflix", "NETFLIX"),
        ("abrir a netflix", "NETFLIX"),
        ("coloca netflix", "NETFLIX"),
        ("vai para netflix", "NETFLIX"),
        ("vai pra netflix", "NETFLIX"),
        ("inicia netflix", "NETFLIX"),
        ("abre max", "MAX"),
        ("abre hbo max", "MAX"),
        ("abrir a max", "MAX"),
        ("abrir hbo", "MAX"),
        ("coloca max", "MAX"),
        ("abre prime", "PRIME_VIDEO"),
        ("abre prime video", "PRIME_VIDEO"),
        ("abre amazon prime", "PRIME_VIDEO"),
        ("abrir prime video", "PRIME_VIDEO"),
        ("abre disney", "DISNEY_PLUS"),
        ("abre disney plus", "DISNEY_PLUS"),
        ("abre disney+", "DISNEY_PLUS"),
        ("abrir disney plus", "DISNEY_PLUS"),
        ("abre youtube", "YOUTUBE"),
        ("abrir youtube", "YOUTUBE"),
        ("vai pro youtube", "YOUTUBE"),
        ("coloca youtube", "YOUTUBE"),
        ("abre spotify", "SPOTIFY"),
        ("abrir spotify", "SPOTIFY"),
        ("abrir o spotify", "SPOTIFY"),
        ("coloca spotify", "SPOTIFY"),
        ("bota spotify", "SPOTIFY"),
        ("botar spotify", "SPOTIFY"),
        ("inicia spotify", "SPOTIFY"),
        ("iniciar spotify", "SPOTIFY"),
        ("quero spotify", "SPOTIFY"),
        ("vai pro spotify", "SPOTIFY"),
        ("vai para o spotify", "SPOTIFY"),
        ("coloca uma música no spotify", "SPOTIFY"),
        ("toca spotify", "SPOTIFY"),
        ("  ABRIR, O   SPOTIFY!!!  ", "SPOTIFY"),
    ],
)
def test_known_platform_commands(command, platform):
    result = parse_command(command)

    assert isinstance(result, OpenPlatformIntent)
    assert result.platform == platform


@pytest.mark.parametrize("command", ["ajuda", "mostrar comandos", "o que você faz"])
def test_help_commands(command):
    assert isinstance(parse_command(command), ShowHelpIntent)


def test_normalization_removes_accents_and_extra_spaces():
    assert normalize_command("  O   QUE   VOCÊ faz  ") == "o que voce faz"


def test_normalization_removes_punctuation_and_expands_plus_symbol():
    assert normalize_command(" Abrir: Disney+!!! ") == "abrir disney plus"


@pytest.mark.parametrize(
    "command",
    [
        "escolhe um filme",
        "abre https://example.com",
        "desliga o computador",
        "powershell shutdown",
        "abre spotify e desliga o computador",
        "",
    ],
)
def test_unknown_commands_preserve_original_text(command):
    result = parse_command(command)

    assert isinstance(result, UnknownIntent)
    assert result.original_text == command


@pytest.mark.parametrize(
    ("command", "platform", "query"),
    [
        ("abre YouTube Kanye West", "YOUTUBE", "Kanye West"),
        (
            "coloca Billie Jean do Michael Jackson no YouTube",
            "YOUTUBE",
            "Billie Jean do Michael Jackson",
        ),
        ("toca Runaway no Spotify", "SPOTIFY", "Runaway"),
        ("procura Kendrick Lamar no Spotify", "SPOTIFY", "Kendrick Lamar"),
        ("PESQUISA Beyoncé no youtube!", "YOUTUBE", "Beyoncé"),
        ("buscar no Spotify Águas de Março", "SPOTIFY", "Águas de Março"),
    ],
)
def test_search_media_commands_extract_platform_and_clean_query(command, platform, query):
    result = parse_command(command)

    assert result == SearchMediaIntent(
        type="SEARCH_MEDIA",
        platform=platform,
        query=query,
    )


@pytest.mark.parametrize(
    "command",
    [
        "pesquisa no YouTube",
        "procura no Spotify",
        "abre Spotify e desliga o computador",
    ],
)
def test_search_media_rejects_empty_or_dangerous_queries(command):
    assert isinstance(parse_command(command), UnknownIntent)


@pytest.mark.parametrize(
    ("command", "platform", "query"),
    [
        ("pesquisa Interestelar na Netflix", "NETFLIX", "Interestelar"),
        ("coloca Stranger Things na Netflix", "NETFLIX", "Stranger Things"),
        ("assistir Breaking Bad na Netflix", "NETFLIX", "Breaking Bad"),
        ("quero assistir Interestelar na Netflix", "NETFLIX", "Interestelar"),
        ("passa One Piece no Prime Video", "PRIME_VIDEO", "One Piece"),
        ("procura The Boys no Amazon Prime", "PRIME_VIDEO", "The Boys"),
    ],
)
def test_search_media_supports_the_streaming_platforms_with_stable_urls(
    command,
    platform,
    query,
):
    assert parse_command(command) == SearchMediaIntent(
        type="SEARCH_MEDIA",
        platform=platform,
        query=query,
    )


@pytest.mark.parametrize(
    ("command", "query"),
    [
        ("Interestelar", "Interestelar"),
        ("Stranger Things", "Stranger Things"),
        ("coloca Interestelar", "Interestelar"),
        ("quero ver Interestelar", "Interestelar"),
        # Max e Disney+ não têm busca: perguntamos onde procurar em vez de
        # responder "não entendi".
        ("coloca The Last of Us no Max", "The Last of Us"),
        ("assistir Loki no Disney+", "Loki"),
    ],
)
def test_content_without_a_usable_platform_asks_where_to_search(command, query):
    assert parse_command(command) == NeedsPlatformIntent(query=query)


def test_music_verb_only_reorders_the_suggestions():
    """"Max" aqui é parte do nome do artista, não a plataforma."""
    assert parse_command("toca Max Richter") == NeedsPlatformIntent(
        query="Max Richter",
        music_hint=True,
    )
    assert parse_command("Interestelar").music_hint is False


@pytest.mark.parametrize("command", ["netflix", "spotify", "disney+"])
def test_a_bare_platform_name_opens_the_platform(command):
    result = parse_command(command)

    assert isinstance(result, OpenPlatformIntent)
