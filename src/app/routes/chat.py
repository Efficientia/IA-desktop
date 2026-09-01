from fastapi import APIRouter
from src.app.schemas import ChatRequest, ChatResponse          # ← adicionar algo que vem do schema
from src.app.graph import executar_fluxo_assistente

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)         # ← response_model
def conversar(requisicao: ChatRequest):    # ← dict vira ChatRequest
    resultado = executar_fluxo_assistente(
        pergunta_usuario=requisicao.pergunta,
        session_id=requisicao.session_id,
    )
    return ChatResponse(
        resposta=resultado["resposta"],
        agentes_chamados=resultado["agentes_chamados"],
    )
