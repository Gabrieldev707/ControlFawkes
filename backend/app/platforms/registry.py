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
