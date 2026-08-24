from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(..., examples=["id_usuario"])
    pergunta:   str = Field(..., min_length=1, examples=["Me dê uma visão geral sobre meus caminhoneiros"])


class ChatResponse(BaseModel):
    resposta:         str
    agentes_chamados: list[str] = Field(default_factory=list)


class SessionResponse(BaseModel):
    session_id: str
    resumo:     str | None = None