from urllib.parse import parse_qs, urlsplit

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


def is_browser_url_allowed(url: str) -> bool:
    if url in BROWSER_ALLOWED_URLS:
        return True

    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.fragment
    ):
        return False

    if parsed.hostname == "www.youtube.com" and parsed.path == "/results":
        query = parse_qs(parsed.query, keep_blank_values=True)
        return set(query) == {"search_query"} and len(query["search_query"]) == 1 and bool(
            query["search_query"][0].strip()
        )

    return (
        parsed.hostname == "open.spotify.com"
        and parsed.path.startswith("/search/")
        and len(parsed.path) > len("/search/")
        and not parsed.query
    )
