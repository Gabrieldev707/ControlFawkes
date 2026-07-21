from dataclasses import dataclass
from typing import Literal, TypeAlias
import unicodedata

from app.schemas.ws import Platform


PLATFORM_ALIASES: dict[Platform, tuple[str, ...]] = {
    "NETFLIX": ("netflix",),
    "MAX": ("max", "hbo max"),
    "PRIME_VIDEO": ("prime", "prime video", "amazon prime"),
    "DISNEY_PLUS": ("disney", "disney plus", "disney+"),
    "YOUTUBE": ("youtube",),
    "SPOTIFY": ("spotify",),
}

PLATFORM_LABELS: dict[Platform, str] = {
    "NETFLIX": "Netflix",
    "MAX": "Max",
    "PRIME_VIDEO": "Prime Video",
    "DISNEY_PLUS": "Disney+",
    "YOUTUBE": "YouTube",
    "SPOTIFY": "Spotify",
}

ACTION_PREFIXES = (
    "abre ",
    "abre a ",
    "abre o ",
    "abrir ",
    "abrir a ",
    "abrir o ",
    "coloca ",
    "vai para ",
    "vai para a ",
    "vai para o ",
    "vai pra ",
    "vai pra a ",
    "vai pra o ",
    "vai pro ",
)

HELP_PHRASES = {
    "ajuda",
    "mostrar comandos",
    "o que voce faz",
}

HELP_COMMANDS = [
    "abre netflix",
    "abre max",
    "abre prime video",
    "abre disney+",
    "abre youtube",
    "abre spotify",
]


@dataclass(frozen=True)
class OpenPlatformIntent:
    type: Literal["OPEN_PLATFORM"]
    platform: Platform


@dataclass(frozen=True)
class ShowHelpIntent:
    type: Literal["SHOW_HELP"] = "SHOW_HELP"


@dataclass(frozen=True)
class UnknownIntent:
    original_text: str
    type: Literal["UNKNOWN"] = "UNKNOWN"


ParsedIntent: TypeAlias = OpenPlatformIntent | ShowHelpIntent | UnknownIntent


def normalize_command(command_text: str) -> str:
    compact = " ".join(command_text.strip().lower().split())
    decomposed = unicodedata.normalize("NFKD", compact)
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def parse_command(command_text: str) -> ParsedIntent:
    normalized = normalize_command(command_text)
    if normalized in HELP_PHRASES:
        return ShowHelpIntent()

    for platform, aliases in PLATFORM_ALIASES.items():
        for prefix in ACTION_PREFIXES:
            if normalized in {f"{prefix}{alias}" for alias in aliases}:
                return OpenPlatformIntent(type="OPEN_PLATFORM", platform=platform)

    return UnknownIntent(original_text=command_text)
