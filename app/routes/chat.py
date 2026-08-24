from fastapi import APIRouter
from app.schemas import ChatRequest, ChatResponse          # ← adicionar algo que vem do schema
from app.graph import executar_fluxo_assessor

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)         # ← response_model
def conversar(requisicao: ChatRequest):    # ← dict vira ChatRequest
    resposta = executar_fluxo_assessor(
        pergunta_usuario=requisicao.pergunta,
        session_id=requisicao.session_id,
    )
    return ChatResponse(
        resposta=resposta,
        agentes_chamados=[str], 
    )
