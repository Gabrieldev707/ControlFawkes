"""Falar de pixel na mesma unidade que o Windows.

O que quebrava: nesta máquina a tela é 1920x1200 com escala de 125%. Para um
processo que não declara consciência de DPI, o Windows finge — `GetWindowRect`
devolvia 1550x926 para uma janela que ocupa 1920x1200 de verdade.

Isso não atrapalhava enquanto tudo era relativo: mirar o centro do vídeo com
`center_of` funciona em qualquer unidade, desde que a conta inteira use a
mesma. A foto da tela quebrou a simetria. O bitmap do `PrintWindow` sai em
pixel físico, então pedir um bitmap de 1550x926 de uma janela de 1920x1200
recorta os 20% de baixo e da direita — e a foto no celular passa a mostrar um
pedaço enquanto a fração é calculada como se fosse a janela inteira.

Resultado medido: tocar num perfil acertava o vizinho, errado por um fator de
1,25. Declarando a consciência, `GetWindowRect` passou a devolver exatamente o
mesmo que o DWM informa como contorno real, e a foto passou a mostrar a janela
toda.

Precisa acontecer antes de qualquer consulta de coordenada, por isso é chamado
na subida do servidor.
"""

from __future__ import annotations

import ctypes
import sys


# PER_MONITOR_AWARE_V2: além de não mentir, é o único modo que acerta janela
# arrastada entre monitores de escalas diferentes.
_PER_MONITOR_AWARE_V2 = -4


def declarar_consciencia_de_dpi() -> bool:
    """Diz ao Windows que este processo fala em pixel de verdade."""
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(_PER_MONITOR_AWARE_V2)):
            return True
    except (AttributeError, OSError):
        # Windows anterior ao 10 1703 não tem a função nova.
        pass

    try:
        # PROCESS_PER_MONITOR_DPI_AWARE, o caminho antigo.
        return ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0
    except (AttributeError, OSError):
        return False
