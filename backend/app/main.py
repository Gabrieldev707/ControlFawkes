from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import health, websocket

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await websocket.dispatcher.startup()
    try:
        yield
    finally:
        await websocket.dispatcher.shutdown()

app = FastAPI(
    title="Fawkes Remote",
    description="API para o controle remoto do Fawkes",
    lifespan=lifespan
)
# Permitir CORS para o frontend local (Vite default: 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(websocket.router)
