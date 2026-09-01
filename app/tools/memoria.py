from app.memory import sessoes
from app.guardrail import guardrail_saida
from langchain.tools import tool
@tool
def buscar_historico(query: str):
    """
    Busca histórico de conversas passadas baseado em uma query.
    Útil para consultar preferências ou decisões do usuário em conversas encerradas.
    """
    # Busca simples baseada em texto no campo 'resumo'
    # Em um cenário real, poderíamos usar busca vetorial (com embeddings)
    # 1. Busca no mongo
    resultados = list(sessoes.find(
        {"resumo": {"$regex": query, "$options": "i"}},
        {"resumo": 1, "session_id": 1, "iniciada_em": 1, "_id": 0}
    ).limit(5))
    
    # 2. Aplicar guardrail nos resumos encontrados
    for r in resultados:
        if r.get("resumo"):
            r["resumo"] = guardrail_saida(r["resumo"], mapa_pii={})["conteudo"]
    
    return resultados


TOOLS_MEMORIA = [buscar_historico]