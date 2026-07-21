import pytest
import os
import tempfile
import uuid
import time
from app.security.device_store import DeviceStore
from app.security.pairing import PairingService

@pytest.fixture
def temp_device_store():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    os.unlink(path) # Delete so it initializes as empty
    lock_path = path + ".lock"
    store = DeviceStore(filepath=path, lockpath=lock_path)
    yield store
    if os.path.exists(path):
        os.unlink(path)
    if os.path.exists(lock_path):
        os.unlink(lock_path)

def test_pin_uninitialized_fails(temp_device_store):
    service = PairingService(temp_device_store)
    assert service.get_current_pin_for_test() is None
    success, _, _, msg = service.attempt_pairing("123456", "Device")
    assert not success
    assert msg == "Serviço de pareamento não inicializado."

def test_initialize_generates_pin_and_prints_once(temp_device_store, capsys):
    service = PairingService(temp_device_store)
    pin1 = service.initialize()
    
    assert pin1 is not None
    assert len(pin1) == 6
    assert pin1.isdigit()
    
    captured = capsys.readouterr()
    assert "CONTROLFAWKES — PAREAMENTO" in captured.out
    assert f"PIN: {pin1}" in captured.out
    assert "Expira em: 5 minutos" in captured.out

    # Call initialize again, it should be idempotent
    pin2 = service.initialize()
    assert pin1 == pin2
    captured_again = capsys.readouterr()
    assert captured_again.out == ""

def test_rotate_pin_explicit(temp_device_store, capsys):
    service = PairingService(temp_device_store)
    pin1 = service.initialize()
    capsys.readouterr() # clear

    pin2 = service.rotate_pin("test")
    assert pin1 != pin2
    captured = capsys.readouterr()
    assert "CONTROLFAWKES — PAREAMENTO" in captured.out
    assert f"PIN: {pin2}" in captured.out

def test_expiration_rotation(temp_device_store, capsys):
    service = PairingService(temp_device_store)
    pin1 = service.initialize()
    capsys.readouterr() # clear
    
    # Simulate expiration
    service.pin_expires_at = time.time() - 10
    rotated = service.rotate_if_expired()
    assert rotated is True
    pin2 = service.get_current_pin_for_test()
    assert pin1 != pin2
    
    captured = capsys.readouterr()
    assert f"PIN: {pin2}" in captured.out

def test_pairing_success_generates_device_id(temp_device_store, capsys):
    service = PairingService(temp_device_store)
    service.initialize()
    pin = service.get_current_pin_for_test()
    capsys.readouterr() # clear
    
    success, device_id, token, msg = service.attempt_pairing(pin, "My iPhone")
    assert success is True
    assert device_id is not None
    assert token is not None
    assert msg == "Pareamento realizado com sucesso."
    
    # Pin should be rotated after success
    new_pin = service.get_current_pin_for_test()
    assert new_pin != pin
    
    captured = capsys.readouterr()
    assert f"PIN: {new_pin}" in captured.out
    assert token not in captured.out # Ensure token is not printed

def test_pairing_five_attempts_rotation(temp_device_store, capsys):
    service = PairingService(temp_device_store)
    service.initialize()
    initial_pin = service.get_current_pin_for_test()
    capsys.readouterr() # clear
    
    for _ in range(4):
        success, _, _, _ = service.attempt_pairing("000000", "Device")
        assert not success
        assert service.get_current_pin_for_test() == initial_pin # Not rotated yet
        
    # 5th attempt should rotate
    success, _, _, msg = service.attempt_pairing("000000", "Device")
    assert not success
    assert "Muitas tentativas falhas" in msg
    new_pin = service.get_current_pin_for_test()
    assert new_pin != initial_pin
    
    captured = capsys.readouterr()
    assert f"PIN: {new_pin}" in captured.out

def test_device_store_authentication(temp_device_store):
    service = PairingService(temp_device_store)
    service.initialize()
    pin = service.get_current_pin_for_test()
    
    success, device_id, token, _ = service.attempt_pairing(pin, "Device")
    assert success
    
    # Store should authenticate
    assert temp_device_store.authenticate_device(device_id, token) is True
    assert temp_device_store.authenticate_device(device_id, "wrong-token") is False
    assert temp_device_store.authenticate_device("wrong-id", token) is False

def test_device_store_revocation(temp_device_store):
    service = PairingService(temp_device_store)
    service.initialize()
    pin = service.get_current_pin_for_test()
    _, device_id, token, _ = service.attempt_pairing(pin, "Device")
    
    assert temp_device_store.authenticate_device(device_id, token) is True
    
    # Revoke
    assert temp_device_store.revoke_device(device_id) is True
    
    # Authenticate after revoke should fail
    assert temp_device_store.authenticate_device(device_id, token) is False
