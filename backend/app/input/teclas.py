"""Teclas que o Windows entrega como o teclado de verdade entregaria.

O detalhe que quebrou os botões de avançar e voltar 10 segundos, medido em
18/08/2026 com Ben 10 no Max: as SETAS são "extended keys".

No teclado físico, seta-esquerda e o 4 do teclado numérico mandam o mesmo
código de varredura (0x4B). O que distingue os dois é um bit — o
`KEYEVENTF_EXTENDEDKEY`. Sem ele, `keybd_event(VK_LEFT, ...)` produz um evento
que o Windows entrega como se viesse do numérico, e um player web que escuta
`ArrowLeft` simplesmente não vê nada acontecer.

É por isso que play/pause funcionava e o seek não: espaço e Escape não são
extended, então o defeito nunca apareceu neles.

O scan code também vai junto. `keybd_event` aceita zero ali e preenche
sozinho, mas alguns aplicativos leem o scan code do evento para decidir se ele
veio de um teclado de verdade — e um zero denuncia a origem sintética.
"""

from __future__ import annotations

import ctypes
import sys


KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

# As teclas que só existem no bloco separado — setas, navegação, Insert e
# Delete. A lista é do Windows, não uma escolha nossa.
TECLAS_ESTENDIDAS: frozenset[int] = frozenset({
    0x21,  # PAGE UP
    0x22,  # PAGE DOWN
    0x23,  # END
    0x24,  # HOME
    0x25,  # LEFT
    0x26,  # UP
    0x27,  # RIGHT
    0x28,  # DOWN
    0x2D,  # INSERT
    0x2E,  # DELETE
})


def scan_code_de(virtual_key: int) -> int:
    """O código de varredura desta tecla, ou zero fora do Windows."""
    if sys.platform != "win32":
        return 0
    try:
        # MAPVK_VK_TO_VSC = 0
        return int(ctypes.windll.user32.MapVirtualKeyW(virtual_key, 0))
    except Exception:  # noqa: BLE001 - sem o mapa, zero é o que já se usava
        return 0


def flags_de(virtual_key: int, soltando: bool = False) -> int:
    """As flags que fazem esta tecla chegar como a de um teclado real."""
    flags = KEYEVENTF_EXTENDEDKEY if virtual_key in TECLAS_ESTENDIDAS else 0
    return flags | (KEYEVENTF_KEYUP if soltando else 0)
