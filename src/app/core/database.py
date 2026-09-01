from src.app.config import MONGODB_URI, MONGO_DB_NAME
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from langgraph.checkpoint.mongodb import MongoDBSaver
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

# ==============================================================================
# CONFIGURAÇÃO DE CONEXÃO MONGODB
# ==============================================================================
MONGO_URI = MONGODB_URI
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