"""Endpoint de voz: recebe o áudio gravado no celular e devolve o texto.

Por que HTTP e não o WebSocket: o protocolo do controle limita cada mensagem a
8 KB, o que é proposital — é o que impede uma conexão de inundar o computador.
Alguns segundos de áudio passam disso com folga, então a voz anda por um canal
próprio, com limite próprio.

A autenticação é a mesma do WebSocket: o par deviceId/token que saiu do
pareamento por PIN. Sem ele, ninguém na rede consegue mandar áudio para cá.
"""

import os
from pathlib import Path
import tempfile

from fastapi import APIRouter, File, Header, HTTPException, Request, UploadFile

from app.media.transcription import (
    MAX_AUDIO_BYTES,
    TranscriptionFailed,
    TranscriptionUnavailable,
    WhisperTranscriber,
    voice_enabled,
)
from app.security.device_store import DeviceStore
from app.security.origins import is_origin_allowed


router = APIRouter()

# Suportados pelo PyAV, que é o que o faster-whisper usa para decodificar.
# O iPhone grava em mp4/aac; Chrome e Firefox, em webm/opus.
ALLOWED_SUFFIXES = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".mp4",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/aac": ".aac",
}
DEFAULT_SUFFIX = ".webm"


class VoiceService:
    """Junta as três peças do endpoint: quem pode, o que aceita, quem transcreve."""

    def __init__(
        self,
        device_store: DeviceStore | None = None,
        transcriber: WhisperTranscriber | None = None,
    ) -> None:
        self.device_store = device_store or DeviceStore()
        self.transcriber = transcriber or WhisperTranscriber()

    def warm_up(self) -> None:
        """Carrega o modelo antes do primeiro comando.

        Falhar aqui não pode derrubar o servidor: sem voz o controle inteiro
        continua funcionando, e o endpoint responde o motivo quando for usado.
        """
        if not voice_enabled():
            return
        try:
            self.transcriber.load()
        except Exception as error:  # noqa: BLE001 - disco, download, memória
            # Qualquer motivo serve para desistir da voz; nenhum serve para
            # derrubar o controle inteiro no startup.
            print(f"[voz] reconhecimento indisponível: {error}", flush=True)


service = VoiceService()


def _suffix_for(content_type: str | None) -> str:
    if not content_type:
        return DEFAULT_SUFFIX
    return ALLOWED_SUFFIXES.get(content_type.split(";")[0].strip().lower(), DEFAULT_SUFFIX)


@router.post("/voice/transcribe")
async def transcribe_voice(
    request: Request,
    audio: UploadFile = File(...),
    x_device_id: str | None = Header(default=None),
    x_device_token: str | None = Header(default=None),
):
    if not voice_enabled():
        raise HTTPException(status_code=503, detail="Comando por voz desativado.")

    if not is_origin_allowed(request.headers.get("origin")):
        raise HTTPException(status_code=403, detail="Origem não permitida.")

    if not x_device_id or not x_device_token:
        raise HTTPException(status_code=401, detail="Autenticação necessária.")
    if not service.device_store.authenticate(x_device_id, x_device_token):
        raise HTTPException(status_code=401, detail="Token inválido.")

    payload = await audio.read(MAX_AUDIO_BYTES + 1)
    if not payload:
        raise HTTPException(status_code=400, detail="Áudio vazio.")
    if len(payload) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Áudio grande demais.")

    # O PyAV lê de arquivo; um temporário evita segurar tudo em memória e some
    # logo em seguida, gravado ou não.
    descriptor, temporary_path = tempfile.mkstemp(
        prefix="fawkes-voice-",
        suffix=_suffix_for(audio.content_type),
    )
    try:
        with os.fdopen(descriptor, "wb") as temporary_file:
            temporary_file.write(payload)
        result = await service.transcriber.transcribe_file(temporary_path)
    except TranscriptionUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except TranscriptionFailed as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        Path(temporary_path).unlink(missing_ok=True)

    # Só espaço em branco conta como silêncio: mandar isso adiante viraria um
    # comando vazio piscando na tela do usuário.
    text = result.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Nada foi dito no áudio.")

    return {  # noqa: RET504
        "text": text,
        "language": result.language,
        "duration": round(result.duration, 2),
    }
