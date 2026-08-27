"""Quais serviços o controle conhece.

Mora sozinho porque `ws.py` reúne as mensagens do protocolo, e as mensagens
precisam do nome dos serviços — inclusive as que vivem em módulos próprios,
como as da tela. Deixar o `Platform` dentro do `ws.py` fazia esses módulos
importarem o `ws`, e o `ws` importar de volta os módulos: um ciclo.

`ws.py` continua reexportando os dois nomes, então quem já importava de lá não
precisa mudar nada.
"""

from typing import Literal


Platform = Literal[
    "NETFLIX",
    "MAX",
    "PRIME_VIDEO",
    "DISNEY_PLUS",
    "YOUTUBE",
    "SPOTIFY",
]

# Plataformas com URL de busca estável e verificada. Max e Disney+ não entram;
# ver a nota em app/platforms/registry.py.
SearchablePlatform = Literal["YOUTUBE", "SPOTIFY", "NETFLIX", "PRIME_VIDEO"]
