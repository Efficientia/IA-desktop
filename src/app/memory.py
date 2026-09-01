import os
from pymongo import MongoClient
from src.app.config import MONGODB_URI, MONGO_DB_NAME
from src.app.llms import llm
from src.app.guardrail import guardrail_saida

from datetime import datetime

# Conexão Global
client = MongoClient(MONGODB_URI or "mongodb://localhost:27017")
db = client[MONGO_DB_NAME or "assessor"]
sessoes = db["sessoes"]
try:
    sessoes.drop_index("session_id_1")
except:
    pass
sessoes.create_index("session_id", unique=True)
sessoes.create_index("iniciada_em")

def iniciar_sessao(session_id):
    """Insere um novo documento de sessão."""
    sessao = {
        "session_id": session_id,
        "iniciada_em": datetime.utcnow(),
        "mensagens": [],
        "resumo": None
    }
    sessoes.insert_one(sessao)
    return sessao

def salvar_mensagem(session_id, role, content):
    """Adiciona uma nova mensagem ao array de mensagens."""
    mensagem = {
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow()
    }
    sessoes.update_one(
        {"session_id": session_id},
        {"$push": {"mensagens": mensagem}}
    )

def encerrar_sessao(session_id):
    """Gera um resumo da sessão e salva."""
    sessao = sessoes.find_one({"session_id": session_id})
    if not sessao or "mensagens" not in sessao:
        return

    # 1. Gerar resumo com LLM
    texto_sessao = "\n".join([f"{m['role']}: {m['content']}" for m in sessao["mensagens"]])
    prompt = f"Faça um resumo desta conversa:\n{texto_sessao}"
    resumo_raw = llm.invoke(prompt).content
    
    # 2. Aplicar Guardrail de Saída (segurança)
    resumo_seguro = guardrail_saida(resumo_raw, mapa_pii={})["conteudo"]

    sessoes.update_one(
        {"session_id": session_id},
        {"$set": {"resumo": resumo_seguro, "encerrada_em": datetime.utcnow()}}
    )
    return resumo_seguro
