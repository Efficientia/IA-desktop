from src.app.memory import iniciar_sessao, salvar_mensagem, encerrar_sessao, sessoes
from src.app.tools.memoria import buscar_historico
import uuid

def test_memory():
    # Clean up
    sessoes.drop()
    print("Coleção limpa.")

    session_id = str(uuid.uuid4())
    print(f"Testando sessão: {session_id}")
    
    # 1. Testar início
    iniciar_sessao(session_id)
    print("Sessão iniciada.")
    
    # 3. Testar encerrar com resumo (agora gera automaticamente via LLM)
    resumo = encerrar_sessao(session_id)
    print(f"Sessão encerrada com resumo: {resumo}")
    print("Mensagens salvas.")
    
    # 3. Testar encerrar com resumo
    encerrar_sessao(session_id, "Usuário gosta de café.")
    print("Sessão encerrada com resumo.")
    
    # 4. Testar busca
    resultados = buscar_historico.invoke({"query": "café"})
    print(f"Resultados da busca: {resultados}")
    
    assert len(resultados) > 0, "Nenhum resultado encontrado!"
    assert any(r['session_id'] == session_id for r in resultados), "Sessão não encontrada na busca!"
    print("Teste passou com sucesso!")

if __name__ == "__main__":
    test_memory()
