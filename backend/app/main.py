from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import health, websocket

app = FastAPI(title="Fawkes Remote", description="API para o controle remoto do Fawkes")

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
