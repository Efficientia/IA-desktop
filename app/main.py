import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega o .env a partir da pasta app/
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Para desenvolvimento, permitido de qualquer lugar
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from app.routes.chat import router as chat_router
app.include_router(chat_router)

# ==============================================================================
# EXECUÇÃO
# ==============================================================================

# Monta os arquivos estáticos do frontend (caminho absoluto para evitar erros)
_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
