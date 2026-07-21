import json
import os
import hashlib
import hmac
import tempfile
from datetime import datetime, timezone
from typing import Dict, Optional
from pydantic import BaseModel, Field
from filelock import FileLock

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
DEVICES_FILE = os.path.join(DATA_DIR, 'paired_devices.json')
LOCK_FILE = os.path.join(DATA_DIR, 'paired_devices.lock')

class DeviceEntry(BaseModel):
    deviceName: str
    tokenHash: str
    createdAt: str
    lastAccess: str

class DeviceStoreModel(BaseModel):
    devices: Dict[str, DeviceEntry] = Field(default_factory=dict)

class DeviceStore:
    def __init__(self, filepath: str = DEVICES_FILE, lockpath: str = LOCK_FILE):
        self.filepath = filepath
        self.lockpath = lockpath
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        self.lock = FileLock(self.lockpath)

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    def _read_unsafe(self) -> Optional[DeviceStoreModel]:
        """Reads the file without locking. Returns None if corrupted, empty model if missing."""
        if not os.path.exists(self.filepath):
            return DeviceStoreModel()
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return DeviceStoreModel.model_validate(data)
        except (json.JSONDecodeError, ValueError, Exception):
            # Fail closed on corruption. Do not overwrite or authorize.
            return None

    def _write_unsafe(self, store: DeviceStoreModel):
        """Writes the file atomically without locking."""
        dir_name = os.path.dirname(self.filepath)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, text=True)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(store.model_dump_json(indent=2))
            os.replace(tmp_path, self.filepath)
        except Exception:
            os.unlink(tmp_path)
            raise

    def add_device(self, device_id: str, device_name: str, token: str) -> bool:
        """Adds a new paired device. Returns True on success, False if file corrupted."""
        with self.lock:
            store = self._read_unsafe()
            if store is None:
                return False  # Corrupted
            
            store.devices[device_id] = DeviceEntry(
                deviceName=device_name,
                tokenHash=self._hash_token(token),
                createdAt=datetime.now(timezone.utc).isoformat(),
                lastAccess=datetime.now(timezone.utc).isoformat()
            )
            self._write_unsafe(store)
            return True

    def authenticate_device(self, device_id: str, token: str) -> bool:
        """Authenticates a device and updates lastAccess. Returns True if valid."""
        with self.lock:
            store = self._read_unsafe()
            if store is None:
                return False
            
            device = store.devices.get(device_id)
            if not device:
                return False
            
            expected_hash = self._hash_token(token)
            if hmac.compare_digest(device.tokenHash, expected_hash):
                # Valid token. Update lastAccess.
                device.lastAccess = datetime.now(timezone.utc).isoformat()
                self._write_unsafe(store)
                return True
            
            return False

    def revoke_device(self, device_id: str) -> bool:
        """Removes a device. Returns True if it was removed, False if not found or corrupt."""
        with self.lock:
            store = self._read_unsafe()
            if store is None:
                return False
            
            if device_id in store.devices:
                del store.devices[device_id]
                self._write_unsafe(store)
                return True
            return False

    def list_devices(self) -> Dict[str, dict]:
        """Lists devices (without hashes) for CLI."""
        with self.lock:
            store = self._read_unsafe()
            if store is None:
                return {}
            
            return {
                d_id: {
                    "deviceName": d.deviceName,
                    "createdAt": d.createdAt,
                    "lastAccess": d.lastAccess
                }
                for d_id, d in store.devices.items()
            }
