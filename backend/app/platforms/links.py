"""Validação de links de mídia enviados pelo usuário.

Só o backend decide se um link é seguro. O frontend manda o texto cru e nunca
uma URL já aprovada.

A validação é por forma, não por confiança no host: exige HTTPS, hostname
exatamente igual a um da lista, path e parâmetros previstos, e um identificador
de vídeo no formato do YouTube. Nada é seguido antes de validar — um redirect
poderia levar a qualquer lugar.
"""

from dataclasses import dataclass
import re
from urllib.parse import parse_qs, urlsplit


# Hostnames exatos. Comparação por igualdade, nunca por sufixo: "endswith"
# aceitaria youtube.com.evil.example.
WATCH_HOSTNAMES = frozenset({
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
})
SHORT_HOSTNAME = "youtu.be"

# IDs de vídeo do YouTube: 11 caracteres do alfabeto base64url.
VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
_VIDEO_ID = VIDEO_ID_PATTERN

# Parâmetros aceitos junto do vídeo. "t" (tempo) é útil e inofensivo; o resto é
# descartado em vez de repassado, para não carregar rastreadores nem redirects.
_ALLOWED_EXTRA_PARAMS = frozenset({"t"})
_TIME_VALUE = re.compile(r"^\d{1,6}s?$")


@dataclass(frozen=True)
class MediaLink:
    platform: str
    url: str
    video_id: str


def _normalized_time(query: dict[str, list[str]]) -> str | None:
    values = query.get("t")
    if not values or len(values) != 1:
        return None
    value = values[0].strip()
    return value if _TIME_VALUE.fullmatch(value) else None


def parse_media_link(text: str) -> MediaLink | None:
    """Retorna o link canônico quando o texto é um link de vídeo permitido."""
    candidate = text.strip()
    if not candidate or len(candidate) > 2048 or any(c.isspace() for c in candidate):
        return None

    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return None

    # Só https. Bloqueia de uma vez file:, javascript:, data: e http.
    if parsed.scheme != "https":
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    if parsed.port is not None:
        return None
    if not parsed.hostname:
        return None

    hostname = parsed.hostname.lower()
    video_id: str | None = None

    if hostname in WATCH_HOSTNAMES and parsed.path == "/watch":
        query = parse_qs(parsed.query, keep_blank_values=True)
        if set(query) - {"v"} - _ALLOWED_EXTRA_PARAMS:
            return None
        values = query.get("v")
        if values and len(values) == 1 and _VIDEO_ID.fullmatch(values[0]):
            video_id = values[0]
    elif hostname == SHORT_HOSTNAME:
        # youtu.be/<id>: o id vem no path.
        path_id = parsed.path.lstrip("/")
        query = parse_qs(parsed.query, keep_blank_values=True)
        if set(query) - _ALLOWED_EXTRA_PARAMS:
            return None
        if _VIDEO_ID.fullmatch(path_id):
            video_id = path_id

    if video_id is None:
        return None

    # Reconstrói a URL a partir do que foi validado, em vez de repassar a
    # original: qualquer parte não reconhecida é descartada, não confiada.
    canonical = f"https://www.youtube.com/watch?v={video_id}"
    start = _normalized_time(parse_qs(parsed.query, keep_blank_values=True))
    if start:
        canonical = f"{canonical}&t={start}"

    return MediaLink(platform="YOUTUBE", url=canonical, video_id=video_id)
