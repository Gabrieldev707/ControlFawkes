"""Validação de Origin do WebSocket.

O middleware de CORS não cobre WebSocket: sem esta checagem, qualquer página
aberta no navegador de alguém da rede consegue abrir um socket e tentar parear.

O que a checagem realmente entrega: um site remoto não consegue forjar Origin,
então bloquear origens não-locais elimina o ataque drive-by. Um cliente nativo
na LAN pode omitir ou falsificar o cabeçalho — contra ele quem defende é o
pareamento (PIN com bloqueio progressivo). Por isso a ausência de Origin é
aceita: recusá-la não impediria ninguém e quebraria clientes legítimos.
"""

from ipaddress import ip_address
import os
from urllib.parse import urlsplit


ALLOWED_ORIGINS_VARIABLE = "FAWKES_ALLOWED_ORIGINS"
LOCAL_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1", "[::1]"})


def _configured_origins() -> frozenset[str]:
    raw = os.environ.get(ALLOWED_ORIGINS_VARIABLE, "")
    return frozenset(origin.strip() for origin in raw.split(",") if origin.strip())


def _is_local_hostname(hostname: str) -> bool:
    if hostname in LOCAL_HOSTNAMES:
        return True
    # Nomes .local (mDNS/Bonjour) resolvem apenas dentro da rede local.
    if hostname.endswith(".local"):
        return True
    try:
        address = ip_address(hostname)
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local


def is_origin_allowed(origin: str | None) -> bool:
    # Clientes não-navegador não enviam Origin; ver docstring do módulo.
    if origin is None:
        return True

    configured = _configured_origins()
    if configured:
        return origin in configured

    if origin == "null":
        return False

    parsed = urlsplit(origin)
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.hostname:
        return False
    return _is_local_hostname(parsed.hostname)
