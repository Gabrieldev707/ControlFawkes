from collections.abc import Callable
from dataclasses import dataclass
import secrets
import time
import uuid

from app.security.device_store import DeviceStore


@dataclass(frozen=True)
class PairingAttempt:
    success: bool
    message: str
    code: str | None = None
    device_id: str | None = None
    token: str | None = None


class PairingService:
    EXPIRATION_SECONDS = 300
    MAX_ATTEMPTS = 5
    LOCKOUT_SECONDS = 60
    MAX_LOCKOUT_SECONDS = 900

    def __init__(
        self,
        device_store: DeviceStore,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.device_store = device_store
        self._clock = clock
        self.current_pin: str | None = None
        self.pin_expires_at = 0.0
        self.failed_attempts = 0
        self.locked_until = 0.0
        self.consecutive_lockouts = 0

    def _lockout_seconds(self) -> int:
        """Dobra a espera a cada bloqueio seguido, até o teto."""
        window = self.LOCKOUT_SECONDS * (2 ** max(0, self.consecutive_lockouts - 1))
        return int(min(window, self.MAX_LOCKOUT_SECONDS))

    def _start_lockout(self) -> int:
        self.consecutive_lockouts += 1
        window = self._lockout_seconds()
        self.locked_until = self._clock() + window
        return window

    def remaining_lockout(self) -> int:
        remaining = self.locked_until - self._clock()
        return max(0, int(remaining) + 1) if remaining > 0 else 0

    def _new_pin(self) -> str:
        previous_pin = self.current_pin
        new_pin = f"{secrets.randbelow(1_000_000):06d}"
        while new_pin == previous_pin:
            new_pin = f"{secrets.randbelow(1_000_000):06d}"
        self.current_pin = new_pin
        self.pin_expires_at = self._clock() + self.EXPIRATION_SECONDS
        self.failed_attempts = 0
        self._print_pin()
        return new_pin

    def _print_pin(self) -> None:
        print("\nCONTROLFAWKES — PAREAMENTO LOCAL")
        print(f"PIN: {self.current_pin}")
        print("Validade: 5 minutos\n")

    def initialize(self) -> str:
        if self.current_pin is None:
            return self._new_pin()
        return self.current_pin

    def attempt(self, pin: str, device_name: str) -> PairingAttempt:
        self.initialize()

        # O bloqueio vem antes de qualquer comparação: é ele que limita a taxa
        # de adivinhação do PIN, que de outro modo seria só a da rede.
        remaining = self.remaining_lockout()
        if remaining > 0:
            return PairingAttempt(
                False,
                f"Muitas tentativas. Aguarde {remaining}s e use o PIN mostrado no computador.",
                "TOO_MANY_ATTEMPTS",
            )

        if self._clock() >= self.pin_expires_at:
            self._new_pin()
            return PairingAttempt(False, "O PIN expirou. Use o novo PIN.", "PIN_EXPIRED")

        if not hmac_safe_equal(pin, self.current_pin or ""):
            self.failed_attempts += 1
            if self.failed_attempts >= self.MAX_ATTEMPTS:
                window = self._start_lockout()
                self._new_pin()
                return PairingAttempt(
                    False,
                    f"Limite de tentativas atingido. Aguarde {window}s e use o novo PIN.",
                    "TOO_MANY_ATTEMPTS",
                )
            return PairingAttempt(False, "PIN incorreto.", "PIN_INVALID")

        device_id = uuid.uuid4().hex
        token = secrets.token_urlsafe(32)
        if not self.device_store.add(device_id, device_name, token):
            return PairingAttempt(False, "Falha ao salvar o dispositivo.", "INTERNAL_ERROR")

        self.consecutive_lockouts = 0
        self._new_pin()
        return PairingAttempt(
            True,
            "Pareamento concluído.",
            device_id=device_id,
            token=token,
        )


def hmac_safe_equal(candidate: str, expected: str) -> bool:
    return secrets.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))
