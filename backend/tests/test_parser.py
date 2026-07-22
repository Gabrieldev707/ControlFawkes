import pytest

from app.commands.parser import (
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
        "pesquisa Interestelar na Netflix",
        "abre Spotify e desliga o computador",
    ],
)
def test_search_media_rejects_empty_unsupported_or_dangerous_queries(command):
    assert isinstance(parse_command(command), UnknownIntent)
