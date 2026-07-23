import pytest

from app.security.origins import ALLOWED_ORIGINS_VARIABLE, is_origin_allowed


@pytest.mark.parametrize("origin", [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://192.168.0.20:5173",   # iPhone na LAN: o caso de uso do MVP
    "http://192.168.1.7:4173",    # vite preview
    "http://10.0.0.5:5173",
    "http://172.20.10.3:5173",    # hotspot pessoal do iPhone
    "http://169.254.10.2:5173",
    "http://fawkes.local:5173",
    "https://192.168.0.20:5173",
])
def test_local_network_origins_are_allowed(origin):
    assert is_origin_allowed(origin) is True


@pytest.mark.parametrize("origin", [
    "https://evil.example",
    "http://evil.example:5173",
    "http://8.8.8.8:5173",
    "http://172.32.0.1:5173",     # fora do bloco privado 172.16/12
    "null",
    "file://",
    "ws://192.168.0.20:5173",
])
def test_remote_and_opaque_origins_are_rejected(origin):
    assert is_origin_allowed(origin) is False


def test_missing_origin_is_allowed_for_non_browser_clients():
    # Recusar não impediria um atacante (basta omitir o cabeçalho) e quebraria
    # clientes legítimos; quem defende esse caso é o PIN com bloqueio.
    assert is_origin_allowed(None) is True


def test_explicit_allowlist_overrides_the_local_network_default(monkeypatch):
    monkeypatch.setenv(ALLOWED_ORIGINS_VARIABLE, "https://fawkes.exemplo.com")

    assert is_origin_allowed("https://fawkes.exemplo.com") is True
    assert is_origin_allowed("http://192.168.0.20:5173") is False
