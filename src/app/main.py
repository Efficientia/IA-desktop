import time
import uuid
import json
import logging
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from src.app.graph import executar_fluxo_assistente

# Configuração de Logging para SRE
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("efficientia_sre")

app = FastAPI(title="Efficientia API")

# --- SERVING FRONTEND ---
# Monta a pasta de arquivos estáticos (CSS, JS)
app.mount("/static", StaticFiles(directory="src/frontend"), name="static")

# Rota para servir o index.html
@app.get("/")
async def read_root():
    return FileResponse("src/frontend/index.html")
# ------------------------

# Middleware para SRE (Latência, Request ID e Taxa de Erro)
@app.middleware("http")
async def sre_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        response = await call_next(request)
        latency = time.time() - start_time
        
        # Log estruturado de sucesso
        logger.info(json.dumps({
            "request_id": request_id,
            "path": request.url.path,
            "latency_seconds": latency,
            "status_code": response.status_code
        }))
        return response
        
    except Exception as e:
        # Log estruturado de erro
        logger.error(json.dumps({
            "request_id": request_id,
            "path": request.url.path,
            "error": str(e)
        }))
        raise HTTPException(status_code=500, detail="Internal Server Error")

class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    message: str

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        # O grafo já gerencia o estado e o MemorySaver
        resposta = executar_fluxo_assistente(
            pergunta_usuario=request.message,
            session_id=request.session_id
        )
        return {"response": resposta}
    except Exception as e:
        logger.error(f"Erro crítico no endpoint /chat: {str(e)}")
        # Retorna uma resposta amigável em vez de 500 Internal Server Error
        return {
            "response": {
                "resposta": "🤖 Ops... tive um problema técnico ao processar sua solicitação (talvez a conexão com o banco?). Por favor, tente novamente em breve.",
                "agentes_chamados": []
            }
        }
