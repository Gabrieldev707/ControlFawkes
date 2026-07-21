import pytest

from app.commands.parser import (
    OpenPlatformIntent,
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
        ("coloca netflix", "NETFLIX"),
        ("vai para netflix", "NETFLIX"),
        ("abre max", "MAX"),
        ("abre hbo max", "MAX"),
        ("abrir a max", "MAX"),
        ("abre prime", "PRIME_VIDEO"),
        ("abre prime video", "PRIME_VIDEO"),
        ("abre amazon prime", "PRIME_VIDEO"),
        ("abre disney", "DISNEY_PLUS"),
        ("abre disney plus", "DISNEY_PLUS"),
        ("abre disney+", "DISNEY_PLUS"),
        ("abre youtube", "YOUTUBE"),
        ("vai pro youtube", "YOUTUBE"),
        ("abre spotify", "SPOTIFY"),
        ("coloca spotify", "SPOTIFY"),
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


@pytest.mark.parametrize(
    "command",
    [
        "escolhe um filme",
        "abre https://example.com",
        "desliga o computador",
        "powershell shutdown",
        "",
    ],
)
def test_unknown_commands_preserve_original_text(command):
    result = parse_command(command)

    assert isinstance(result, UnknownIntent)
    assert result.original_text == command
