from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.api import voice
from app.api.voice import VoiceService, router
from app.media.transcription import (
    MAX_AUDIO_BYTES,
    Transcription,
    TranscriptionFailed,
    TranscriptionUnavailable,
    WhisperTranscriber,
)


class FakeDeviceStore:
    def __init__(self, devices: dict[str, str] | None = None) -> None:
        self.devices = devices if devices is not None else {"device-1": "token-1"}

    def authenticate(self, device_id: str, token: str) -> bool:
        return self.devices.get(device_id) == token


class FakeTranscriber:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result or Transcription(text="abre a Netflix", language="pt", duration=1.4)
        self.error = error
        self.calls: list[str] = []

    async def transcribe_file(self, audio_path: str) -> Transcription:
        self.calls.append(audio_path)
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def client(monkeypatch):
    def build(transcriber=None, devices=None):
        service = VoiceService(
            device_store=FakeDeviceStore(devices),
            transcriber=transcriber or FakeTranscriber(),
        )
        monkeypatch.setattr(voice, "service", service)
        app = FastAPI()
        app.include_router(router)
        return TestClient(app), service

    return build


AUTH = {"X-Device-Id": "device-1", "X-Device-Token": "token-1"}


def post(test_client, headers=AUTH, payload=b"audio-falso"):
    return test_client.post(
        "/voice/transcribe",
        headers=headers,
        files={"audio": ("comando.webm", payload, "audio/webm")},
    )


def test_transcribes_audio_from_a_paired_device(client):
    test_client, _ = client()

    response = post(test_client)

    assert response.status_code == 200
    assert response.json()["text"] == "abre a Netflix"


def test_rejects_audio_without_credentials(client):
    test_client, _ = client()

    assert post(test_client, headers={}).status_code == 401


def test_rejects_audio_from_an_unknown_device(client):
    """O endpoint de voz é uma porta a mais para o computador; ela usa o mesmo
    token do pareamento, senão bastaria estar na rede para mandar áudio."""
    test_client, _ = client()

    response = post(test_client, headers={"X-Device-Id": "device-1", "X-Device-Token": "errado"})

    assert response.status_code == 401


def test_rejects_a_remote_origin(client):
    test_client, _ = client()

    response = test_client.post(
        "/voice/transcribe",
        headers={**AUTH, "Origin": "https://site-qualquer.com"},
        files={"audio": ("comando.webm", b"audio", "audio/webm")},
    )

    assert response.status_code == 403


def test_accepts_an_origin_from_the_local_network(client):
    test_client, _ = client()

    response = test_client.post(
        "/voice/transcribe",
        headers={**AUTH, "Origin": "http://192.168.0.14:5173"},
        files={"audio": ("comando.webm", b"audio", "audio/webm")},
    )

    assert response.status_code == 200


def test_rejects_audio_above_the_size_limit(client):
    test_client, _ = client()

    response = post(test_client, payload=b"x" * (MAX_AUDIO_BYTES + 1))

    assert response.status_code == 413


def test_rejects_empty_audio(client):
    test_client, _ = client()

    assert post(test_client, payload=b"").status_code == 400


def test_reports_when_the_model_is_not_available(client):
    test_client, _ = client(
        transcriber=FakeTranscriber(error=TranscriptionUnavailable("sem modelo")),
    )

    response = post(test_client)

    assert response.status_code == 503
    assert "sem modelo" in response.json()["detail"]


def test_reports_audio_it_could_not_understand(client):
    test_client, _ = client(
        transcriber=FakeTranscriber(error=TranscriptionFailed("áudio ruim")),
    )

    assert post(test_client).status_code == 422


def test_reports_silence_instead_of_sending_an_empty_command(client):
    """Texto vazio viraria um comando em branco na tela do usuário."""
    test_client, _ = client(
        transcriber=FakeTranscriber(
            result=Transcription(text="   ", language="pt", duration=0.4),
        ),
    )

    assert post(test_client).status_code == 422


def test_the_temporary_audio_file_never_survives_the_request(client):
    transcriber = FakeTranscriber()
    test_client, _ = client(transcriber=transcriber)

    post(test_client)

    assert transcriber.calls
    assert not Path(transcriber.calls[0]).exists()


def test_the_extension_follows_the_content_type_so_pyav_can_decode(client):
    """O iPhone manda mp4; salvar tudo como .webm confundia o decodificador."""
    transcriber = FakeTranscriber()
    test_client, _ = client(transcriber=transcriber)

    test_client.post(
        "/voice/transcribe",
        headers=AUTH,
        files={"audio": ("comando.mp4", b"audio", "audio/mp4")},
    )

    assert transcriber.calls[0].endswith(".mp4")


def test_voice_can_be_turned_off_entirely(client, monkeypatch):
    monkeypatch.setenv("CONTROLFAWKES_VOICE", "off")
    test_client, _ = client()

    assert post(test_client).status_code == 503


def test_warm_up_does_not_crash_the_server_when_the_model_is_missing():
    """Sem voz o controle inteiro continua funcionando; derrubar o startup por
    causa dela seria trocar um recurso por todos."""

    def broken_factory():
        raise RuntimeError("sem disco")

    service = VoiceService(
        device_store=FakeDeviceStore(),
        transcriber=WhisperTranscriber(model_factory=broken_factory),
    )

    service.warm_up()
