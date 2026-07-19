# Fawkes Remote

Este repositório contém o módulo independente do **Fawkes Remote**.
O sistema é dividido em duas partes:

1. **Frontend**: Aplicação React mobile-first que atua como controle remoto.
2. **Backend**: Servidor FastAPI responsável pela comunicação com o SO e websocket.

## Setup

### Backend (Python)
```bash
cd backend
python -m venv .venv
# Ativar venv e instalar dependências
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload
```

### Frontend (React/Vite)
```bash
cd frontend
npm install
npm run dev
```
