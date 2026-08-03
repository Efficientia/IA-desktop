import os
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver

from sys_prompt import PERSONA_SISTEMA

# ==============================================================================
# CONFIGURAÇÃO
# ==============================================================================

load_dotenv()

llm_gemini = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.4,
    top_p=0.95,
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

llm_groq = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.4,
    top_p=0.95,
    api_key=os.getenv("GROQ_API_KEY"),
)

# Gemini é o principal.
# Caso esteja indisponível, utiliza o Groq.
llm = llm_gemini.with_fallbacks([llm_groq])

# ==============================================================================
# MEMÓRIA
# ==============================================================================

checkpointer = MemorySaver()

# ==============================================================================
# AGENTE
# ==============================================================================

app = create_agent(
    model=llm,
    tools=[],
    system_prompt=PERSONA_SISTEMA,
    checkpointer=checkpointer,
)

# ==============================================================================
# EXECUÇÃO
# ==============================================================================

THREAD_ID = "eficientia"

print("=" * 60)
print("EficientIA iniciada.")
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