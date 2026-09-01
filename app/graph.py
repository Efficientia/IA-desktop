import operator
from typing import Annotated, TypedDict
from app.llms import llm_gemini, llm_groq, llm_rapido, llm_especialista
from langgraph.graph import StateGraph, END
from langgraph.graph.message import MessagesState
from langchain_core.messages import RemoveMessage
from langgraph.prebuilt import create_react_agent


import os

from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig
from app.tools.analise_dados import TOOLS
from app.tools.faq_tools import faq_retriever
from app.tools.memoria import TOOLS_MEMORIA
from app.tools.planejamento import TOOLS_AGENDA
from app.memory import salvar_mensagem
from app.core.prompts import (
    ROUTER_PROMPT_COMPLETO,
    ANALISE_DADOS_PROMPT_COMPLETO,
    PLANEJAMENTO_PROMPT_COMPLETO,
    ORQUESTRADOR_PROMPT_COMPLETO,
    FAQ_PROMPT_COMPLETO,
)
from app.guardrail import guardrail_entrada, guardrail_saida, anonimizar_entrada, desanonimizar_saida
from datetime import datetime


agora = datetime.now().strftime("%H:%M:%S")


router_app       = create_react_agent(model=llm_rapido,       tools=TOOLS_MEMORIA,                prompt=ROUTER_PROMPT_COMPLETO)
analise_dados_app = create_react_agent(model=llm_especialista, tools=TOOLS + TOOLS_MEMORIA,        prompt=ANALISE_DADOS_PROMPT_COMPLETO)
planejamento_app  = create_react_agent(model=llm_especialista, tools=TOOLS_AGENDA + TOOLS_MEMORIA, prompt=PLANEJAMENTO_PROMPT_COMPLETO)
orquestrador_app = create_react_agent(model=llm_rapido,       tools=[],                            prompt=ORQUESTRADOR_PROMPT_COMPLETO)
faq_app          = create_react_agent(model=llm_rapido,       tools=[faq_retriever],               prompt=FAQ_PROMPT_COMPLETO)

# ==============================================================================
# ESTADO
# ==============================================================================
class Estado(MessagesState):                                  # ID da sessão
    agentes_chamados:   Annotated[list[str], operator.add]  # acumula entre nós
    rota: str
    mapa_pii: dict
    input: str                 # pergunta (já anonimizada) repassada entre os nós
    resposta_final: str        # resposta que será devolvida ao usuário
    saida_especialista: str    # saída do agente especialista, antes do orquestrador

# ==============================================================================



# ==============================================================================
# NÓS
# ==============================================================================
def no_roteador(estado: Estado, config: RunnableConfig) -> dict:
    # O `config` é injetado pelo LangGraph nos nós que o declaram na assinatura.
    # Precisa ser repassado à mão: diferente de financeiro/agenda, que são nós do
    # grafo (add_node) e herdam o config sozinhos, o router_app é chamado dentro
    # de uma função comum. Sem esta linha a tool buscar_historico não recebe o
    # thread_id/user_id e não consegue identificar de quem é o histórico.
    saida = router_app.invoke({"messages": list(estado["messages"])}, config=config)
    texto = saida["messages"][-1].text

    # Resposta direta (saudação, fora de escopo): já escreve no campo final
    if not texto.strip().startswith("ROUTE="):
        return {
            "agentes_chamados": ["roteador"],
            "resposta_final":   texto,
        }

    # Encaminhamento: sobrescreve input com o protocolo para o especialista
    return {
        "input":            texto,
        "agentes_chamados": ["roteador"],
    }


def no_analise_dados(estado: Estado, config: RunnableConfig) -> dict:
    # Nó do grafo (add_node): o LangGraph injeta `config` sozinho — só
    # precisa ser repassado à chamada interna do agente especialista.
    saida = analise_dados_app.invoke(
        {"messages": [{"role": "human", "content": estado["input"]}]},
        config=config,
    )
    return {
        "saida_especialista": saida["messages"][-1].text,
        "agentes_chamados":   ["analise_dados"],
    }


def no_planejamento(estado: Estado, config: RunnableConfig) -> dict:
    saida = planejamento_app.invoke(
        {"messages": [{"role": "human", "content": estado["input"]}]},
        config=config,
    )
    return {
        "saida_especialista": saida["messages"][-1].text,
        "agentes_chamados":   ["planejamento"],
    }


def no_faq(estado: Estado, config: RunnableConfig) -> dict:
    saida = faq_app.invoke(
        {"messages": [{"role": "human", "content": estado["input"]}]},
        config=config,
    )
    return {
        "saida_especialista": saida["messages"][-1].text,
        "resposta_final":     saida["messages"][-1].text,  # bypassa o orquestrador
        "agentes_chamados":   ["faq"],
    }


def no_orquestrador(estado: Estado, config: RunnableConfig) -> dict:
    saida = orquestrador_app.invoke(
        {"messages": [{"role": "human", "content": estado["saida_especialista"]}]},
        config=config,
    )
    return {
        "resposta_final":   saida["messages"][-1].text,
        "agentes_chamados": ["orquestrador"],
    }


# === Quero e TENHO que estudar isso ===

def no_guardrail(estado: Estado) -> dict:
    msg_usuario = estado["messages"][-1]
    puser = msg_usuario.content
    anonimizado, novo_mapa = anonimizar_entrada(puser)

    resposta = guardrail_entrada(anonimizado)
    if resposta["bloqueado"]:
        return {
            "resposta_final": resposta["mensagem"],
            "agentes_chamados": ["guardrail_entrada"],
            "messages": [{"role": "system", "content": f"[GUARDRAIL BLOQUEOU] Motivo: {resposta['motivo']}"}],
        }
    else:
        return {
            "input": anonimizado,
            "mapa_pii": novo_mapa,
            "agentes_chamados": ["guardrail_entrada"],
            # Remove a mensagem original (com o dado real) e insere no lugar
            # dela a versão anonimizada — assim o roteador e os especialistas
            # nunca veem o texto original com PII, mas o histórico continua
            # tendo a mensagem do usuário (só que anonimizada).
            "messages": [
                RemoveMessage(id=msg_usuario.id),
                {"role": "human", "content": anonimizado},
            ],
        }


def no_guardrail_saida(estado: Estado) -> dict:
    resultado = guardrail_saida(estado["resposta_final"], estado["mapa_pii"])
    return {
        "messages": [{"role": "system", "content": f"[GUARDRAIL REVISOU SAÍDA] Resultado: {resultado['motivo']}"}],
        "resposta_final": resultado["conteudo"]
    }

def roteador_guardrail_entrd(estado: Estado) -> str:
    if estado.get("resposta_final") == "fim":
        return "fim"
    return "roteador"


# === ^^^^^^^^^^ Quero e TENHO que estudar isso ^^^^^^^^^^ ===


# ==============================================================================
# FUNÇÃO DE DECISÃO
# ==============================================================================
def decidir_especialista(estado: Estado) -> str:
    """Lê o protocolo do roteador e devolve o nome do próximo nó."""
    texto = estado["input"].strip()

    if not texto.startswith("ROUTE="):
        return "fim"   # resposta direta já foi escrita no nó do roteador

    rota = texto.split("\n", 1)[0].split("=", 1)[1].strip()
    return rota if rota in ("analise_dados", "planejamento", "faq") else "fim"




# ==============================================================================
# CONSTRUÇÃO DO GRAFO
# ==============================================================================
grafo = StateGraph(Estado)

grafo.add_node("roteador",     no_roteador)
grafo.add_node("analise_dados",   no_analise_dados)
grafo.add_node("planejamento",    no_planejamento)
grafo.add_node("faq",          no_faq)
grafo.add_node("orquestrador", no_orquestrador)
grafo.add_node("guardrail_entrd", no_guardrail)
grafo.add_node("guardrail_saida", no_guardrail_saida)

grafo.set_entry_point("guardrail_entrd")

grafo.add_conditional_edges(
    "guardrail_entrd",
    roteador_guardrail_entrd,
    {
        "roteador": "roteador",
        "fim":      END,   # bloqueio na entrada: resposta do guardrail já é final
    },
)

grafo.add_conditional_edges(
    "roteador",
    decidir_especialista,
    {
        "analise_dados": "analise_dados",
        "planejamento":     "planejamento",
        "faq":        "faq",
        "fim":        END,       # resposta direta: sem especialista nem orquestrador
    },
)

grafo.add_edge("analise_dados",   "orquestrador")
grafo.add_edge("planejamento",    "orquestrador")
grafo.add_edge("orquestrador", "guardrail_saida")
grafo.add_edge("guardrail_saida", END)   # resposta do orquestrador passa pelo guardrail de saída para revisão final
grafo.add_edge("faq",          END)

# Memória centralizada no grafo — persiste o Estado inteiro entre turns
memory = MemorySaver()
fluxo_agentes = grafo.compile(checkpointer=memory)



# ==============================================================================
# FLUXO PRINCIPAL
# ==============================================================================
def executar_fluxo_assistente(pergunta_usuario: str, session_id: str) -> dict:
    estado_inicial = {
        "messages": [{"role": "human", "content": pergunta_usuario}],
        "agentes_chamados":   [],
        "rota": "",
        "mapa_pii": {},
    }

    estado_final = fluxo_agentes.invoke(
        estado_inicial,
        config={"configurable": {"thread_id": session_id}},
    )

    print(f"[debug] agentes chamados: {estado_final['agentes_chamados']}")
    return {
        "resposta": estado_final["resposta_final"],
        "agentes_chamados": estado_final["agentes_chamados"],
    }



# # ==============================================================================
# # LOOP DE CONVERSA
# # ==============================================================================
# while True:
#     try:
#         user_input = input("> ")
#         if user_input.lower() in ("sair", "end", "fim", "tchau", "bye"):
#             print("Encerrando a conversa.")
#             break

#         resposta = executar_fluxo_assessor(
#             pergunta_usuario=user_input,
#             session_id="id_usuario_mas_agora_não_importa",
#         )
#         print(resposta)

#     except Exception as e:
#         print("Erro ao consumir a API:", e)
#         continue