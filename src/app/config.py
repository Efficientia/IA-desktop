import os
from pathlib import Path
from dotenv import load_dotenv

# BASE_DIR aponta para migracao_fastAPI/. Montado a partir da localização
# do próprio arquivo: não depende da pasta de onde você rodou o uvicorn.
BASE_DIR     = Path(__file__).resolve().parent
DATA_DIR     = BASE_DIR / "data"

print(f"DEBUG: BASE_DIR={BASE_DIR}")
load_dotenv(BASE_DIR / ".env")
print(f"DEBUG: GEMINI_API_KEY={os.getenv('GEMINI_API_KEY')}")

DATA_DIR     = BASE_DIR / "data"

FAQ_PATH = DATA_DIR / "FAQ_gestao_v1.1.pdf"



GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY    = os.getenv("GROQ_API_KEY")
GOOGLE_API_KEY  = os.getenv("GOOGLE_API_KEY", GEMINI_API_KEY)
DATABASE_URL    = os.getenv("DATABASE_URL")
MONGODB_URI     = os.getenv("MONGO_URI")
MONGO_DB_NAME   = os.getenv("MONGO_DB_NAME", "gestao_dados")
MONGO_IP        = os.getenv("MONGO_IP")
MONGO_USER      = os.getenv("MONGO_USER")
MONGO_PASSWORD  = os.getenv("MONGO_PASSWORD")

OBRIGATORIAS = {
    "GEMINI_API_KEY": GEMINI_API_KEY,
    "GROQ_API_KEY":   GROQ_API_KEY,
    "GOOGLE_API_KEY": GOOGLE_API_KEY,
    "DATABASE_URL":   DATABASE_URL,
    "MONGODB_URI":    MONGODB_URI,
    "MONGO_DB_NAME":  MONGO_DB_NAME,
    "MONGO_IP":       MONGO_IP,
    "MONGO_USER":     MONGO_USER,
    "MONGO_PASSWORD": MONGO_PASSWORD,
}


def validar_config() -> list[str]:
    """Devolve a lista de problemas de configuração (vazia = tudo certo)."""
    problemas = []
    for nome, valor in OBRIGATORIAS.items():
        if not valor:
            problemas.append(f"Variável ausente no .env: {nome}")
    if not FAQ_PATH.exists():
        problemas.append(f"FAQ não encontrado em: {FAQ_PATH}")
    return problemas