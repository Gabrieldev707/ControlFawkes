import json
import re

from app.security.device_store import DeviceStore
from app.security.pairing import PairingService


class MutableClock:
    def __init__(self, now: float = 1_000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


def make_store(tmp_path):
    return DeviceStore(
        filepath=tmp_path / "paired_devices.json",
        lockpath=tmp_path / "paired_devices.lock",
    )


def invalid_pin_for(pairing):
    return "000000" if pairing.current_pin != "000000" else "111111"


def test_initialize_generates_six_digit_pin(tmp_path):
    pairing = PairingService(make_store(tmp_path))

    pin = pairing.initialize()

    assert re.fullmatch(r"\d{6}", pin)


def test_correct_pin_is_single_use_and_token_authenticates(tmp_path):
    store = make_store(tmp_path)
    pairing = PairingService(store)
    pin = pairing.initialize()

    result = pairing.attempt(pin, "iPhone")

    assert result.success is True
    assert result.device_id
    assert result.token
    assert store.authenticate(result.device_id, result.token) is True
    assert pairing.attempt(pin, "Outro iPhone").code == "PIN_INVALID"


def test_incorrect_pin_is_rejected(tmp_path):
    pairing = PairingService(make_store(tmp_path))
    pairing.initialize()

    result = pairing.attempt(invalid_pin_for(pairing), "iPhone")

    assert result.success is False
    assert result.code == "PIN_INVALID"


def test_expired_pin_is_rejected_and_rotated(tmp_path):
    clock = MutableClock()
    pairing = PairingService(make_store(tmp_path), clock=clock)
    expired_pin = pairing.initialize()
    clock.now += 301

    result = pairing.attempt(expired_pin, "iPhone")

    assert result.success is False
    assert result.code == "PIN_EXPIRED"
    assert pairing.current_pin != expired_pin


def test_fifth_failed_attempt_rotates_pin(tmp_path):
    pairing = PairingService(make_store(tmp_path))
    initial_pin = pairing.initialize()

    invalid_pin = invalid_pin_for(pairing)
    for _ in range(4):
        assert pairing.attempt(invalid_pin, "iPhone").code == "PIN_INVALID"
    result = pairing.attempt(invalid_pin, "iPhone")

    assert result.code == "TOO_MANY_ATTEMPTS"
    assert pairing.current_pin != initial_pin


def test_device_store_never_persists_raw_token(tmp_path):
    path = tmp_path / "paired_devices.json"
    store = DeviceStore(filepath=path, lockpath=tmp_path / "paired_devices.lock")

    assert store.add("device-1", "iPhone", "raw-secret-token") is True

    persisted = path.read_text(encoding="utf-8")
    assert "raw-secret-token" not in persisted
    assert json.loads(persisted)["devices"]["device-1"]["tokenHash"]


def test_invalid_and_revoked_tokens_are_rejected(tmp_path):
    store = make_store(tmp_path)
    store.add("device-1", "iPhone", "valid-token")

    assert store.authenticate("device-1", "invalid-token") is False
    assert store.authenticate("missing-device", "valid-token") is False
    assert store.revoke("device-1") is True
    assert store.authenticate("device-1", "valid-token") is False
    assert store.revoke("device-1") is False


def test_device_listing_omits_token_hashes(tmp_path):
    store = make_store(tmp_path)
    store.add("device-1", "iPhone", "valid-token")

    devices = store.list_devices()

    assert devices["device-1"]["deviceName"] == "iPhone"
    assert "tokenHash" not in devices["device-1"]
