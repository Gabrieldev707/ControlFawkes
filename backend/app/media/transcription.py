"""Transcrição de voz local, com o Whisper da OpenAI.

Roda inteiramente na máquina: o áudio gravado no celular vai para o computador
que já está pareado e nunca sai dele. É a mesma promessa do resto do
ControlFawkes — nada de serviço externo no meio.

O runtime é o faster-whisper (CTranslate2), que executa os pesos do Whisper
bem mais rápido que a implementação de referência em CPU. O modelo é o mesmo.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import os
import threading


DEFAULT_MODEL = "small"
DEFAULT_LANGUAGE = "pt"
# int8 é o que torna o Whisper utilizável em CPU: comandos curtos saem em ~1s
# em vez de vários segundos, com perda de qualidade irrelevante nessa escala.
DEFAULT_COMPUTE_TYPE = "int8"

MODEL_VARIABLE = "CONTROLFAWKES_WHISPER_MODEL"
LANGUAGE_VARIABLE = "CONTROLFAWKES_WHISPER_LANGUAGE"
COMPUTE_TYPE_VARIABLE = "CONTROLFAWKES_WHISPER_COMPUTE"
THREADS_VARIABLE = "CONTROLFAWKES_WHISPER_THREADS"
ENABLED_VARIABLE = "CONTROLFAWKES_VOICE"

# Comando de controle remoto é curto. O teto existe para que um upload grande
# não prenda a CPU do computador inteiro num pedido só.
MAX_AUDIO_BYTES = 8 * 1024 * 1024
MAX_AUDIO_SECONDS = 30.0


class TranscriptionUnavailable(RuntimeError):
    """O reconhecimento de voz não está disponível nesta máquina."""


class TranscriptionFailed(RuntimeError):
    """O áudio chegou, mas não foi possível transcrever."""


@dataclass(frozen=True)
class Transcription:
    text: str
    language: str
    duration: float


def _int_from_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip())
    except ValueError:
        return default


def voice_enabled() -> bool:
    """Voz ligada por padrão; `CONTROLFAWKES_VOICE=off` desliga."""
    return os.environ.get(ENABLED_VARIABLE, "on").strip().lower() not in {
        "off",
        "0",
        "false",
        "no",
    }


ModelFactory = Callable[[], object]


class WhisperTranscriber:
    """Carrega o modelo uma vez e reaproveita entre pedidos.

    A carga leva alguns segundos e é feita sob um lock: dois comandos de voz
    quase simultâneos no primeiro uso carregariam o modelo duas vezes, dobrando
    memória e tempo.
    """

    def __init__(
        self,
        model_name: str | None = None,
        language: str | None = None,
        compute_type: str | None = None,
        model_factory: ModelFactory | None = None,
    ) -> None:
        self.model_name = model_name or os.environ.get(MODEL_VARIABLE, DEFAULT_MODEL)
        self.language = language or os.environ.get(LANGUAGE_VARIABLE, DEFAULT_LANGUAGE)
        self.compute_type = compute_type or os.environ.get(
            COMPUTE_TYPE_VARIABLE, DEFAULT_COMPUTE_TYPE,
        )
        # 0 deixa o CTranslate2 decidir. Vale mexer só se a máquina estiver
        # dividindo a CPU com outra coisa pesada: aí um número menor costuma
        # render mais do que deixar as threads brigarem entre si.
        self.cpu_threads = _int_from_env(THREADS_VARIABLE, 0)
        self._model_factory = model_factory
        self._model: object | None = None
        self._load_lock = threading.Lock()

    def _build_model(self):
        if self._model_factory is not None:
            return self._model_factory()
        try:
            from faster_whisper import WhisperModel
        except ImportError as error:
            raise TranscriptionUnavailable(
                "faster-whisper não está instalado. Rode: pip install faster-whisper",
            ) from error
        try:
            return WhisperModel(
                self.model_name,
                device="cpu",
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads,
            )
        except Exception as error:  # noqa: BLE001 - download, disco, modelo inválido
            raise TranscriptionUnavailable(
                f"Não foi possível carregar o modelo '{self.model_name}'.",
            ) from error

    def load(self):
        """Carrega o modelo agora. Chamado no startup para o primeiro comando
        de voz não pagar a espera da carga."""
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is None:
                self._model = self._build_model()
        return self._model

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def _transcribe_blocking(self, audio_path: str) -> Transcription:
        model = self.load()
        try:
            segments, info = model.transcribe(  # type: ignore[attr-defined]
                audio_path,
                language=self.language,
                beam_size=1,
                vad_filter=True,
                # Sem isso o Whisper preenche silêncio com frases inventadas —
                # normalmente legendas de vídeo do conjunto de treino. Num
                # controle remoto isso viraria um comando fantasma.
                condition_on_previous_text=False,
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
        except Exception as error:  # noqa: BLE001 - áudio corrompido, formato etc.
            raise TranscriptionFailed("Não foi possível entender o áudio.") from error

        duration = float(getattr(info, "duration", 0.0) or 0.0)
        if duration > MAX_AUDIO_SECONDS:
            raise TranscriptionFailed("Áudio longo demais para um comando.")

        return Transcription(
            text=text,
            language=str(getattr(info, "language", self.language) or self.language),
            duration=duration,
        )

    async def transcribe_file(self, audio_path: str) -> Transcription:
        # Fora do event loop: a transcrição é CPU pura e travaria todo o resto
        # do controle (ponteiro, teclado, direcional) enquanto rodasse.
        return await asyncio.to_thread(self._transcribe_blocking, audio_path)
