from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import health, websocket


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await websocket.dispatcher.startup()
    yield


app = FastAPI(
    title="Fawkes Remote",
    description="API local para o controle remoto do Fawkes",
    lifespan=lifespan,
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
