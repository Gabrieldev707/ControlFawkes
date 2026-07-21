import hashlib
import hmac
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from filelock import FileLock


DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_DEVICES_FILE = DEFAULT_DATA_DIR / "paired_devices.json"


class DeviceStore:
    def __init__(
        self,
        filepath: str | Path = DEFAULT_DEVICES_FILE,
        lockpath: str | Path | None = None,
    ) -> None:
        self.filepath = Path(filepath)
        self.lockpath = Path(lockpath) if lockpath else self.filepath.with_suffix(".lock")
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self._lock = FileLock(str(self.lockpath))

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _read_unlocked(self) -> dict[str, Any] | None:
        if not self.filepath.exists():
            return {"devices": {}}
        try:
            data = json.loads(self.filepath.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict) or not isinstance(data.get("devices"), dict):
            return None
        return data

    def _write_unlocked(self, data: dict[str, Any]) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.filepath.parent,
            prefix="paired_devices-",
            suffix=".tmp",
            text=True,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
                json.dump(data, temporary_file, ensure_ascii=False, indent=2)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_name, self.filepath)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def add(self, device_id: str, device_name: str, token: str) -> bool:
        with self._lock:
            data = self._read_unlocked()
            if data is None:
                return False
            now = datetime.now(timezone.utc).isoformat()
            data["devices"][device_id] = {
                "deviceName": device_name,
                "tokenHash": self._hash_token(token),
                "createdAt": now,
                "lastAccess": now,
            }
            self._write_unlocked(data)
            return True

    def authenticate(self, device_id: str, token: str) -> bool:
        with self._lock:
            data = self._read_unlocked()
            if data is None:
                return False
            device = data["devices"].get(device_id)
            if not isinstance(device, dict) or not isinstance(device.get("tokenHash"), str):
                return False
            if not hmac.compare_digest(device["tokenHash"], self._hash_token(token)):
                return False
            device["lastAccess"] = datetime.now(timezone.utc).isoformat()
            self._write_unlocked(data)
            return True

    def revoke(self, device_id: str) -> bool:
        with self._lock:
            data = self._read_unlocked()
            if data is None or device_id not in data["devices"]:
                return False
            del data["devices"][device_id]
            self._write_unlocked(data)
            return True

    def list_devices(self) -> dict[str, dict[str, str]]:
        with self._lock:
            data = self._read_unlocked()
            if data is None:
                return {}
            return {
                device_id: {
                    "deviceName": record["deviceName"],
                    "createdAt": record["createdAt"],
                    "lastAccess": record["lastAccess"],
                }
                for device_id, record in data["devices"].items()
                if isinstance(record, dict)
                and all(key in record for key in ("deviceName", "createdAt", "lastAccess"))
            }
