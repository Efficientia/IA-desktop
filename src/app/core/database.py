import os
import re
import logging
from src.app.config import MONGO_URI, MONGO_DB_NAME, DATABASE_URL
from sqlalchemy import create_engine, text
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from langgraph.checkpoint.mongodb import MongoDBSaver
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

logger = logging.getLogger("efficientia_sre")

# ==============================================================================
# CONFIGURAÇÃO DE CONEXÃO MONGODB
# ==============================================================================
MONGO_URI = MONGO_URI
DB_NAME = MONGO_DB_NAME

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

# ==============================================================================
# CHECKPOINTER PARA O LANGGRAPH (Substitui o MemorySaver)
# ==============================================================================
# O MongoDBSaver gerencia as coleções 'checkpoints' e 'checkpoint_writes' nativamente.
# Para usá-lo no main.py, você passará esta instância como checkpointer.
sync_client = client.delegate  # O MongoDBSaver precisa do cliente síncrono subjacente
langgraph_checkpointer = MongoDBSaver(sync_client, db_name=DB_NAME)

# ==============================================================================
# MODELOS PYDANTIC PARA HISTÓRICO ANALÍTICO
# ==============================================================================

class ThreadModel(BaseModel):
    thread_id: str
    usuario_id: Optional[str] = None
    placa_veiculo: Optional[str] = None
    status: str = "ativa"
    criado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    atualizado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MessageModel(BaseModel):
    thread_id: str
    role: str # "user", "assistant", "tool"
    agente_origem: Optional[str] = None # ex: "roteador", "orquestrador", "motorista"
    content: str
    json_orquestrador: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ==============================================================================
# FUNÇÕES DE MANIPULAÇÃO DE MEMÓRIA (OPCIONAIS/AUXILIARES)
# ==============================================================================

async def criar_ou_atualizar_thread(thread_id: str, usuario_id: str = None):
    """
    Registra uma nova sessão de atendimento para vincular aos dados do motorista.
    """
    thread = await db.threads.find_one({"thread_id": thread_id})
    if not thread:
        nova_thread = ThreadModel(thread_id=thread_id, usuario_id=usuario_id)
        await db.threads.insert_one(nova_thread.model_dump())
    else:
        await db.threads.update_one(
            {"thread_id": thread_id},
            {"$set": {"atualizado_em": datetime.now(timezone.utc)}}
        )

async def salvar_mensagem_historico(mensagem: MessageModel):
    """
    Salva a mensagem estruturada para posterior análise de BI e geração de dashboards.
    """
    await db.messages.insert_one(mensagem.model_dump())
    await criar_ou_atualizar_thread(mensagem.thread_id)

# ==============================================================================
# CONFIGURAÇÃO DE CONEXÃO POSTGRESQL
# ==============================================================================
_pg_engine = None


def _normalizar_url_postgres(url: str) -> str:
    """
    Valida e normaliza a DATABASE_URL para o formato aceito pelo SQLAlchemy:
        postgresql+psycopg2://usuario:senha@host:porta/banco
    """
    url = url.strip().strip('"').strip("'")

    # URL no formato JDBC (Java) não funciona no SQLAlchemy/psycopg2.
    if url.startswith("jdbc:"):
        raise ValueError(
            "DATABASE_URL está em formato JDBC ('jdbc:...'). Use o formato "
            "'postgresql+psycopg2://usuario:senha@host:porta/banco'. "
            "No Supabase: Connect > URI (Session pooler)."
        )

    # 'postgres://' (legado) e 'postgresql://' sem driver -> psycopg2 explícito
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

    if not url.startswith("postgresql"):
        raise ValueError(
            "DATABASE_URL inválida: deve começar com 'postgresql+psycopg2://'."
        )

    # Sem '@' não há usuário/senha na URL (erro comum ao copiar string JDBC)
    if "@" not in url:
        raise ValueError(
            "DATABASE_URL sem usuário e senha. Formato esperado: "
            "postgresql+psycopg2://usuario:senha@host:porta/banco "
            "(no pooler do Supabase o usuário é 'postgres.<project-ref>')."
        )

    return url


def _testar_engine(url: str):
    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return engine


def get_postgres_engine():
    """
    Retorna a engine do SQLAlchemy para conexão ao banco de dados PostgreSQL.
    Possui suporte a reconexão automática e fallback para pooler do Supabase.
    """
    global _pg_engine
    if _pg_engine is not None:
        return _pg_engine

    url_original = DATABASE_URL or os.getenv("DATABASE_URL")
    if not url_original:
        raise ValueError("DATABASE_URL não configurada no ambiente.")

    # Se a URL estiver em formato inválido, o erro já é claro e explicativo.
    url = _normalizar_url_postgres(url_original)

    try:
        _pg_engine = _testar_engine(url)
        return _pg_engine
    except Exception:
        # Registra o erro REAL (antes ele era engolido pelo fallback/raise)
        logger.exception("Falha ao conectar no PostgreSQL com a DATABASE_URL configurada")

        # Fallback para pooler Supabase caso a resolução direta do host falhe
        # (host direto: db.<ref>.supabase.co)
        match = re.search(
            r"postgresql(?:\+psycopg2)?://([^:]+):([^@]+)@db\.([a-z0-9]+)\.supabase\.co:(\d+)/(.*)",
            url,
        )
        if match:
            user, pwd, ref, port, db_name = match.groups()
            pooler_url = (
                f"postgresql+psycopg2://{user}.{ref}:{pwd}"
                f"@aws-0-sa-east-1.pooler.supabase.com:6543/{db_name}"
            )
            try:
                _pg_engine = _testar_engine(pooler_url)
                return _pg_engine
            except Exception:
                logger.exception("Falha também no fallback via pooler do Supabase")
                raise
        raise