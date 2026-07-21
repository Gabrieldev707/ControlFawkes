from dataclasses import dataclass
from typing import Literal, TypeAlias
import unicodedata

from app.schemas.ws import Platform


PLATFORM_ALIASES: dict[Platform, tuple[str, ...]] = {
    "NETFLIX": ("netflix",),
    "MAX": ("max", "hbo", "hbo max"),
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
    "abre",
    "abrir",
    "coloca",
    "bota",
    "botar",
    "inicia",
    "iniciar",
    "quero",
    "toca",
    "vai para",
    "vai pra",
    "vai pro",
)

ARTICLES = {
    "a",
    "as",
    "o",
    "os",
    "um",
    "uma",
    "uns",
    "umas",
    "ao",
    "aos",
    "na",
    "nas",
    "no",
    "nos",
}

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
    expanded = command_text.strip().lower().replace("+", " plus ")
    decomposed = unicodedata.normalize("NFKD", expanded)
    without_accents = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    without_punctuation = "".join(
        character if character.isalnum() or character.isspace() else " "
        for character in without_accents
    )
    return " ".join(without_punctuation.split())


def _remove_articles(command_text: str) -> str:
    return " ".join(
        token
        for token in command_text.split()
        if token not in ARTICLES
    )


def parse_command(command_text: str) -> ParsedIntent:
    normalized = normalize_command(command_text)
    if normalized in HELP_PHRASES:
        return ShowHelpIntent()

    canonical = _remove_articles(normalized)
    for platform, aliases in PLATFORM_ALIASES.items():
        platform_prefixes = ACTION_PREFIXES
        if platform == "SPOTIFY":
            platform_prefixes += ("coloca musica",)

        canonical_aliases = {
            _remove_articles(normalize_command(alias))
            for alias in aliases
        }
        for prefix in platform_prefixes:
            if canonical in {f"{prefix} {alias}" for alias in canonical_aliases}:
                return OpenPlatformIntent(type="OPEN_PLATFORM", platform=platform)

    return UnknownIntent(original_text=command_text)
