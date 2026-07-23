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
    # Verbos de vídeo: as frases mais naturais para filme e série.
    "quero assistir",
    "quero ver",
    "assistir",
    "assiste",
    "ver",
    "passa",
    "passar",
)
_SEARCH_VERB_PATTERN = "|".join(
    sorted((re.escape(verb) for verb in SEARCH_VERBS), key=len, reverse=True)
)
# Plataformas com URL de busca estável e verificada. Max e Disney+ ficam de
# fora; ver a nota em app/platforms/registry.py.
SEARCHABLE_PLATFORMS: tuple[Platform, ...] = (
    "YOUTUBE",
    "SPOTIFY",
    "NETFLIX",
    "PRIME_VIDEO",
)


def _alias_pattern(platforms: tuple[Platform, ...]) -> str:
    aliases = {
        alias
        for platform in platforms
        for alias in PLATFORM_ALIASES[platform]
    }
    # Do mais longo para o mais curto: "prime video" antes de "prime".
    return "|".join(sorted((re.escape(alias) for alias in aliases), key=len, reverse=True))


def _platform_for_alias(alias: str) -> Platform | None:
    normalized = " ".join(alias.lower().split())
    for platform, aliases in PLATFORM_ALIASES.items():
        if normalized in aliases:
            return platform
    return None


_ALL_PLATFORMS: tuple[Platform, ...] = tuple(PLATFORM_ALIASES)

# O prefixo aceita apenas plataformas pesquisáveis. Sem a preposição, o nome da
# plataforma é ambíguo demais: em "toca Max Richter", "max" é parte do artista,
# não o destino da busca.
_SEARCH_PREFIX = re.compile(
    rf"^\s*(?:{_SEARCH_VERB_PATTERN})\s+"
    rf"(?:(?:no|na|em|para\s+o|pro|o|a)\s+)?"
    rf"(?P<platform>{_alias_pattern(SEARCHABLE_PLATFORMS)})\b"
    rf"(?:\s+(?P<query>.*?))?\s*[.!?]*$",
    re.IGNORECASE,
)

# O sufixo aceita todas as plataformas: a preposição desfaz a ambiguidade. Se a
# plataforma não tiver busca, ainda assim extraímos a consulta e perguntamos
# onde procurar, em vez de responder "não entendi".
_SEARCH_SUFFIX = re.compile(
    rf"^\s*(?:{_SEARCH_VERB_PATTERN})\s+"
    rf"(?P<query>.+?)\s+"
    rf"(?:no|na|em|para\s+o|pro)\s+"
    rf"(?P<platform>{_alias_pattern(_ALL_PLATFORMS)})\s*[.!?]*$",
    re.IGNORECASE,
)
_EMPTY_SEARCH_QUERIES = {"musica", "uma musica", "algo"}

# Pedidos vagos, já sem artigos: não há o que pesquisar, então não faz sentido
# perguntar em qual plataforma procurar.
_VAGUE_QUERIES = {
    "algo",
    "alguma coisa",
    "qualquer coisa",
    "coisa",
    "musica",
    "filme",
    "serie",
    "escolhe algo",
    "escolhe filme",
    "escolhe serie",
    "escolhe musica",
    "quero assistir",
    "assistir",
}
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
    platform: Literal["YOUTUBE", "SPOTIFY", "NETFLIX", "PRIME_VIDEO"]
    query: str


@dataclass(frozen=True)
class NeedsPlatformIntent:
    """Há uma consulta clara, mas nenhuma plataforma utilizável foi indicada.

    Cobre tanto "Interestelar" quanto "coloca Interestelar no Max", já que o
    Max não tem busca. Nos dois casos perguntamos onde procurar em vez de
    escolher por conta própria.

    `music_hint` sai do verbo que o usuário escolheu ("toca"), não de uma
    classificação do conteúdo: serve apenas para ordenar as sugestões.
    """

    query: str
    music_hint: bool = False
    type: Literal["NEEDS_PLATFORM"] = "NEEDS_PLATFORM"


ParsedIntent: TypeAlias = (
    OpenPlatformIntent
    | SearchMediaIntent
    | NeedsPlatformIntent
    | ShowHelpIntent
    | UnknownIntent
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


def _clean_query(raw_query: str | None) -> str | None:
    if raw_query is None:
        return None
    query = raw_query.strip(" \t\r\n.,!?;:\"'")
    normalized = normalize_command(query)
    if not normalized or normalized in _EMPTY_SEARCH_QUERIES:
        return None
    if any(fragment in normalized for fragment in _UNSAFE_SEARCH_FRAGMENTS):
        return None
    return query


def _parse_search_media(
    command_text: str,
) -> SearchMediaIntent | NeedsPlatformIntent | None:
    match = _SEARCH_SUFFIX.fullmatch(command_text) or _SEARCH_PREFIX.fullmatch(command_text)
    if match is None:
        return None

    query = _clean_query(match.group("query"))
    if query is None:
        return None

    platform = _platform_for_alias(match.group("platform"))
    if platform is None or platform not in SEARCHABLE_PLATFORMS:
        # Plataforma citada, mas sem busca utilizável: pergunta onde procurar.
        return NeedsPlatformIntent(
            query=query,
            music_hint=_has_music_verb(command_text),
        )

    return SearchMediaIntent(
        type="SEARCH_MEDIA",
        platform=platform,  # type: ignore[arg-type]
        query=query,
    )


_LEADING_VERBS = tuple(sorted(
    set(SEARCH_VERBS) | set(ACTION_PREFIXES),
    key=len,
    reverse=True,
))
_MAX_QUERY_LENGTH = 200

# "... no Spotify" / "... na Netflix": a menção à plataforma não faz parte da
# consulta. Sem isso, "procura no Spotify" pesquisaria por "no Spotify".
_TRAILING_PLATFORM = re.compile(
    rf"(?:^|\s+)(?:no|na|em|para\s+o|pro)\s+"
    rf"(?:{_alias_pattern(_ALL_PLATFORMS)})\s*[.!?]*$",
    re.IGNORECASE,
)


MUSIC_VERBS = ("toca", "tocar", "coloca musica", "poe musica", "escuta", "escutar")


def _has_music_verb(command_text: str) -> bool:
    normalized = normalize_command(command_text)
    return any(
        normalized == verb or normalized.startswith(f"{verb} ")
        for verb in MUSIC_VERBS
    )


def _parse_needs_platform(command_text: str, canonical: str) -> NeedsPlatformIntent | None:
    """Texto livre que descreve um conteúdo, sem plataforma utilizável."""
    if canonical in _VAGUE_QUERIES:
        return None

    stripped = command_text.strip()
    # Remove um verbo de ação inicial: "coloca Interestelar" -> "Interestelar".
    for verb in _LEADING_VERBS:
        pattern = re.compile(rf"^\s*{re.escape(verb)}\s+", re.IGNORECASE)
        if pattern.match(stripped):
            stripped = pattern.sub("", stripped, count=1)
            break

    stripped = _TRAILING_PLATFORM.sub("", stripped, count=1).strip()
    query = _clean_query(stripped)
    if query is None or len(query) > _MAX_QUERY_LENGTH:
        return None
    if _remove_articles(normalize_command(query)) in _VAGUE_QUERIES:
        return None
    return NeedsPlatformIntent(
        query=query,
        music_hint=_has_music_verb(command_text),
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
        if canonical in canonical_aliases:
            # Só o nome da plataforma ("netflix") abre a plataforma.
            return OpenPlatformIntent(type="OPEN_PLATFORM", platform=platform)

    needs_platform = _parse_needs_platform(command_text, canonical)
    if needs_platform is not None:
        return needs_platform

    return UnknownIntent(original_text=command_text)
