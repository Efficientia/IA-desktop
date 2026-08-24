import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega o .env a partir da pasta app/
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI

from app.llms import llm_gemini, llm_groq, llm_rapido, llm_especialista, llm
from langchain.agents import create_agent

from app.core.prompts import PERSONA_SISTEMA, ROUTER_PROMPT_COMPLETO, FAQ_PROMPT_COMPLETO
from app.tools.faq_tools import faq_retriever
from app.core.database import langgraph_checkpointer # <-- Importação da memória MongoDB

api = FastAPI()

@api.get("/")
def read_root():
    return {"message": "EficientIA API is running"}

# Para rodar com FastAPI: uvicorn app.main:api --reload

# ==============================================================================
# CONFIGURAÇÃO
# ==============================================================================

load_dotenv()



# ==============================================================================
# MEMÓRIA E AGENTE PRINCIPAL
# ==============================================================================

# O agente principal agora utiliza o checkpointer persistente no MongoDB
app = create_agent(
    model=llm,
    tools=[],
    system_prompt=PERSONA_SISTEMA,
    checkpointer=langgraph_checkpointer,
)

# ==============================================================================
# EXECUÇÃO
# ==============================================================================

THREAD_ID = "eficientia_sessao_001"

print("=" * 60)
print("EficientIA iniciada com memória em MongoDB.")
print("Digite 'sair' para encerrar.")
print("=" * 60)

while True:

    pergunta = input("\nVocê: ").strip()

    if pergunta.lower() in {"sair", "exit", "quit"}:
        print("\nEncerrando...")
        break

    try:

        resposta = app.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": pergunta
                    }
                ]
            },
            config={
                "configurable": {
                    "thread_id": THREAD_ID
                }
            }
        )

        print("\nIA:\n")

        print(resposta["messages"][-1].text)

    except KeyboardInterrupt:
        print("\nEncerrado.")
        break

    except Exception as erro:
        print(f"\nErro: {erro}")