from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import bridge, catalog, health, now_playing, profile, screen, voice, websocket
from .security.instancia_unica import JaEstaRodando, TravaDeInstancia
from .security.origins import cors_origin_settings
from .windows.dpi import declarar_consciencia_de_dpi


# Antes de qualquer consulta de coordenada: numa tela com escala, um processo
# que não declara isso recebe medidas fingidas do Windows, e a foto da tela
# sai recortada sem nenhum erro aparecer. Ver app/windows/dpi.py.
declarar_consciencia_de_dpi()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Antes de tudo: um segundo servidor conta o tempo assistido duas vezes, e
    # no Windows ele sobe calado, porque dois processos conseguem escutar a
    # mesma porta. Ver app/security/instancia_unica.py.
    trava = TravaDeInstancia()
    try:
        trava.tomar()
    except JaEstaRodando as erro:
        print(f"\n{erro}\n", flush=True)
        raise

    # O segredo da ponte nasce aqui, na primeira execução. Gerar no startup e
    # não sob demanda evita a corrida em que host e servidor criam credenciais
    # diferentes ao mesmo tempo — e o segredo NUNCA é impresso.
    bridge.credencial.garantir()

    await websocket.dispatcher.startup()
    # O modelo de voz leva alguns segundos para carregar. Aquecer em segundo
    # plano deixa o servidor atender de imediato e evita que o primeiro comando
    # de voz pague essa espera.
    warm_up = asyncio.create_task(asyncio.to_thread(voice.service.warm_up))
    try:
        yield
    finally:
        warm_up.cancel()
        await websocket.dispatcher.shutdown()
        trava.soltar()


app = FastAPI(
    title="Fawkes Remote",
    description="API local para o controle remoto do Fawkes",
    lifespan=lifespan,
)

# A mesma política de origem do WebSocket. Antes só `localhost:5173` era
# aceito, o que bastava para o navegador do próprio computador e barrava o
# celular, cuja origem é o IP da rede local.
allowed_origins, allowed_origin_regex = cors_origin_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
# O CORS acima vale para o app inteiro, e para esta rota ele não é a defesa: um
# `fetch` de página nem chega a precisar de CORS para SAIR. Quem barra navegador
# aqui é a própria rota — loopback, ausência de `Origin` e credencial. Ver a
# docstring de `api/bridge.py`.
app.include_router(bridge.router)
app.include_router(catalog.router)
app.include_router(now_playing.router)
app.include_router(profile.router)
app.include_router(screen.router)
app.include_router(voice.router)
app.include_router(websocket.router)
