import secrets
import time
from typing import Optional, Tuple
from app.security.device_store import DeviceStore

class PairingService:
    def __init__(self, device_store: DeviceStore):
        self.device_store = device_store
        self.current_pin: Optional[str] = None
        self.pin_expires_at: float = 0.0
        self.attempts: int = 0
        self.MAX_ATTEMPTS = 5
        self.EXPIRATION_SECONDS = 300  # 5 minutes

    def _generate_pin(self) -> str:
        # Generate exactly 6 digits with leading zeros
        return f"{secrets.randbelow(1000000):06d}"

    def _print_banner(self):
        print("\n" + "="*48)
        print("CONTROLFAWKES — PAREAMENTO\n")
        print(f"PIN: {self.current_pin}")
        print(f"Expira em: {self.EXPIRATION_SECONDS // 60} minutos\n")
        print("Abra o ControlFawkes no celular e digite este PIN.")
        print("="*48 + "\n")

    def initialize(self) -> str:
        """Gera e anuncia o primeiro PIN uma única vez; chamadas seguintes são idempotentes."""
        if self.current_pin is None:
            self.current_pin = self._generate_pin()
            self.pin_expires_at = time.time() + self.EXPIRATION_SECONDS
            self.attempts = 0
            self._print_banner()
        return self.current_pin

    def rotate_pin(self, reason: str) -> str:
        """Gera, armazena e anuncia um novo PIN por uma razão conhecida."""
        self.current_pin = self._generate_pin()
        self.pin_expires_at = time.time() + self.EXPIRATION_SECONDS
        self.attempts = 0
        self._print_banner()
        return self.current_pin

    def rotate_if_expired(self) -> bool:
        """Rotaciona se expirado e informa se houve rotação."""
        if self.current_pin is not None and time.time() > self.pin_expires_at:
            self.rotate_pin("expiração")
            return True
        return False

    def get_current_pin_for_test(self) -> Optional[str]:
        """Test only method. Do not expose via network."""
        return self.current_pin

    def attempt_pairing(self, pin: str, device_name: str) -> Tuple[bool, Optional[str], Optional[str], str]:
        """
        Validates the PIN. If valid, generates a device_id and token, saves to DeviceStore, and rotates PIN.
        Returns (success, device_id, token, message).
        """
        if self.current_pin is None:
            return False, None, None, "Serviço de pareamento não inicializado."

        self.rotate_if_expired()

        if self.attempts >= self.MAX_ATTEMPTS:
            self.rotate_pin("excesso de tentativas")
            return False, None, None, "Muitas tentativas falhas. Novo PIN gerado."

        if pin != self.current_pin:
            self.attempts += 1
            if self.attempts >= self.MAX_ATTEMPTS:
                self.rotate_pin("excesso de tentativas")
                return False, None, None, "Muitas tentativas falhas. Novo PIN gerado."
            return False, None, None, "PIN incorreto."

        # PIN is correct!
        import uuid
        device_id = uuid.uuid4().hex
        token = secrets.token_urlsafe(32)
        success = self.device_store.add_device(device_id, device_name, token)
        
        # Always rotate after success
        self.rotate_pin("pareamento bem-sucedido")

        if success:
            return True, device_id, token, "Pareamento realizado com sucesso."
        else:
            return False, None, None, "Falha ao registrar dispositivo (armazenamento corrompido)."
