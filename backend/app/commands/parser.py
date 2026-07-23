from dataclasses import dataclass
import re
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
    "pesquisa Kanye West no YouTube",
    "toca Runaway no Spotify",
]

SEARCH_VERBS = (
    "abre",
    "abrir",
    "coloca",
    "colocar",
    "bota",
    "botar",
    "toca",
    "tocar",
    "pesquisa",
    "pesquisar",
    "procura",
    "procurar",
    "busca",
    "buscar",
    "põe",
    "poe",
)
_SEARCH_VERB_PATTERN = "|".join(
    sorted((re.escape(verb) for verb in SEARCH_VERBS), key=len, reverse=True)
)
_SEARCH_PLATFORM_PATTERN = r"youtube|spotify"
_SEARCH_PREFIX = re.compile(
    rf"^\s*(?:{_SEARCH_VERB_PATTERN})\s+"
    rf"(?:(?:no|na|em|para\s+o|pro|o|a)\s+)?"
    rf"(?P<platform>{_SEARCH_PLATFORM_PATTERN})\b"
    rf"(?:\s+(?P<query>.*?))?\s*[.!?]*$",
    re.IGNORECASE,
)
_SEARCH_SUFFIX = re.compile(
    rf"^\s*(?:{_SEARCH_VERB_PATTERN})\s+"
    rf"(?P<query>.+?)\s+"
    rf"(?:no|na|em|para\s+o|pro)\s+"
    rf"(?P<platform>{_SEARCH_PLATFORM_PATTERN})\s*[.!?]*$",
    re.IGNORECASE,
)
_EMPTY_SEARCH_QUERIES = {"musica", "uma musica", "algo"}
_UNSAFE_SEARCH_FRAGMENTS = {
    "http",
    "https",
    "powershell",
    "shutdown",
    "desliga o computador",
    "reinicia o computador",
}


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


@dataclass(frozen=True)
class SearchMediaIntent:
    type: Literal["SEARCH_MEDIA"]
    platform: Literal["YOUTUBE", "SPOTIFY"]
    query: str


ParsedIntent: TypeAlias = (
    OpenPlatformIntent | SearchMediaIntent | ShowHelpIntent | UnknownIntent
)


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


def _parse_search_media(command_text: str) -> SearchMediaIntent | None:
    match = _SEARCH_SUFFIX.fullmatch(command_text) or _SEARCH_PREFIX.fullmatch(command_text)
    if match is None:
        return None

    raw_query = match.group("query")
    if raw_query is None:
        return None
    query = raw_query.strip(" \t\r\n.,!?;:\"'")
    normalized_query = normalize_command(query)
    if not normalized_query or normalized_query in _EMPTY_SEARCH_QUERIES:
        return None
    if any(fragment in normalized_query for fragment in _UNSAFE_SEARCH_FRAGMENTS):
        return None

    platform = match.group("platform").lower()
    return SearchMediaIntent(
        type="SEARCH_MEDIA",
        platform="YOUTUBE" if platform == "youtube" else "SPOTIFY",
        query=query,
    )


def parse_command(command_text: str) -> ParsedIntent:
    normalized = normalize_command(command_text)
    if normalized in HELP_PHRASES:
        return ShowHelpIntent()

    search_intent = _parse_search_media(command_text)
    if search_intent is not None:
        return search_intent

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
