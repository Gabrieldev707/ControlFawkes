from typing import Literal, TypeAlias


MediaAction: TypeAlias = Literal[
    "MEDIA_PLAY_PAUSE",
    "MEDIA_PREVIOUS",
    "MEDIA_NEXT",
    "MEDIA_SEEK_BACK",
    "MEDIA_SEEK_FORWARD",
    "MEDIA_FULLSCREEN",
    "MEDIA_EXIT_FULLSCREEN",
]

MEDIA_ACTIONS: tuple[MediaAction, ...] = (
    "MEDIA_PLAY_PAUSE",
    "MEDIA_PREVIOUS",
    "MEDIA_NEXT",
    "MEDIA_SEEK_BACK",
    "MEDIA_SEEK_FORWARD",
    "MEDIA_FULLSCREEN",
    "MEDIA_EXIT_FULLSCREEN",
)

MEDIA_ACTION_LABELS: dict[MediaAction, str] = {
    "MEDIA_PLAY_PAUSE": "Play/pause",
    "MEDIA_PREVIOUS": "Faixa anterior",
    "MEDIA_NEXT": "Próxima faixa",
    "MEDIA_SEEK_BACK": "Retrocesso de 10 segundos",
    "MEDIA_SEEK_FORWARD": "Avanço de 10 segundos",
    "MEDIA_FULLSCREEN": "Fullscreen",
    "MEDIA_EXIT_FULLSCREEN": "Saída do fullscreen",
}
