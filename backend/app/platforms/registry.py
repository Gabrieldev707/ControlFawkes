from urllib.parse import parse_qs, quote, urlencode, urlsplit

from app.platforms.links import VIDEO_ID_PATTERN
from app.schemas.ws import Platform


PLATFORM_URLS: dict[Platform, str] = {
    "SPOTIFY": "https://open.spotify.com",
    "YOUTUBE": "https://www.youtube.com",
    "NETFLIX": "https://www.netflix.com",
    "MAX": "https://www.max.com",
    "PRIME_VIDEO": "https://www.primevideo.com",
    "DISNEY_PLUS": "https://www.disneyplus.com",
}

BROWSER_PLATFORMS: frozenset[Platform] = frozenset({
    "YOUTUBE",
    "NETFLIX",
    "MAX",
    "PRIME_VIDEO",
    "DISNEY_PLUS",
})

BROWSER_PLATFORM_URLS: frozenset[str] = frozenset(
    PLATFORM_URLS[platform] for platform in BROWSER_PLATFORMS
)

BROWSER_ALLOWED_URLS: frozenset[str] = (
    BROWSER_PLATFORM_URLS | {PLATFORM_URLS["SPOTIFY"]}
)


# Busca por parâmetro de query: (hostname exato, path exato, único parâmetro aceito).
#
# Max e Disney+ ficam de fora de propósito: nenhum dos dois expõe uma URL de
# busca estável. `www.max.com/search` redireciona para `www.hbomax.com/search`,
# que responde 404, e `play.max.com/search` descarta a consulta; em Disney+,
# `/search` responde 404 e `/browse/search` cai numa página de UUID que também
# responde 404. Preferimos não ter busca a mandar o usuário para uma página
# quebrada. Ver docs/PHASE2_PROGRESS.md.
QUERY_SEARCH_SPECS: dict[Platform, tuple[str, str, str]] = {
    "YOUTUBE": ("www.youtube.com", "/results", "search_query"),
    "NETFLIX": ("www.netflix.com", "/search", "q"),
    "PRIME_VIDEO": ("www.primevideo.com", "/search", "phrase"),
}

# Busca por path: (hostname exato, prefixo do path). A consulta vai no path.
PATH_SEARCH_SPECS: dict[Platform, tuple[str, str]] = {
    "SPOTIFY": ("open.spotify.com", "/search/"),
}

SEARCH_PLATFORMS: frozenset[Platform] = (
    frozenset(QUERY_SEARCH_SPECS) | frozenset(PATH_SEARCH_SPECS)
)


def build_search_url(platform: Platform, query: str) -> str | None:
    """Monta a URL de busca da plataforma. None quando não há busca suportada.

    É a única origem de URL de busca: o frontend manda plataforma e consulta,
    nunca uma URL.
    """
    normalized = query.strip()
    if not normalized:
        return None

    if platform in QUERY_SEARCH_SPECS:
        hostname, path, parameter = QUERY_SEARCH_SPECS[platform]
        return f"https://{hostname}{path}?{urlencode({parameter: normalized})}"

    if platform in PATH_SEARCH_SPECS:
        hostname, prefix = PATH_SEARCH_SPECS[platform]
        return f"https://{hostname}{prefix}{quote(normalized, safe='')}"

    return None


# Ordem padrão das sugestões: vídeo primeiro, porque a maioria das consultas
# livres é título de filme ou série.
_VIDEO_FIRST: tuple[Platform, ...] = ("NETFLIX", "PRIME_VIDEO", "YOUTUBE", "SPOTIFY")
_MUSIC_FIRST: tuple[Platform, ...] = ("SPOTIFY", "YOUTUBE", "NETFLIX", "PRIME_VIDEO")


def suggested_search_platforms(music_hint: bool = False) -> list[Platform]:
    """Plataformas oferecidas quando o usuário não disse onde procurar.

    `music_hint` vem do verbo usado ("toca"), nunca de uma classificação do
    conteúdo: apenas reordena, sem remover opções.
    """
    return list(_MUSIC_FIRST if music_hint else _VIDEO_FIRST)


# Links de vídeo canônicos, montados por app/platforms/links.py a partir de um
# id validado. O parâmetro "t" (tempo) é opcional.
_WATCH_SPEC = ("www.youtube.com", "/watch", "v")


def _is_allowed_watch_url(parsed) -> bool:
    hostname, path, parameter = _WATCH_SPEC
    if parsed.hostname != hostname or parsed.path != path:
        return False
    query = parse_qs(parsed.query, keep_blank_values=True)
    if set(query) - {parameter, "t"}:
        return False
    values = query.get(parameter)
    # Mesmo formato exigido pelo parser de links: as duas camadas concordam, e
    # nenhum /watch com id arbitrário passa por aqui.
    return bool(values) and len(values) == 1 and bool(VIDEO_ID_PATTERN.fullmatch(values[0]))


def _has_safe_shape(url: str) -> tuple[bool, object]:
    parsed = urlsplit(url)
    safe = not (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.fragment
    )
    return safe, parsed


def is_browser_url_allowed(url: str) -> bool:
    if url in BROWSER_ALLOWED_URLS:
        return True

    safe, parsed = _has_safe_shape(url)
    if not safe:
        return False

    if _is_allowed_watch_url(parsed):
        return True

    for hostname, path, parameter in QUERY_SEARCH_SPECS.values():
        if parsed.hostname == hostname and parsed.path == path:
            query = parse_qs(parsed.query, keep_blank_values=True)
            return (
                set(query) == {parameter}
                and len(query[parameter]) == 1
                and bool(query[parameter][0].strip())
            )

    for hostname, prefix in PATH_SEARCH_SPECS.values():
        if (
            parsed.hostname == hostname
            and parsed.path.startswith(prefix)
            and len(parsed.path) > len(prefix)
            and not parsed.query
        ):
            return True

    return False
