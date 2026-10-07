import operator
from typing import Annotated, TypedDict
from src.app.llms import llm_gemini, llm_groq, llm_rapido, llm_especialista
from langgraph.graph import StateGraph, END
from langgraph.graph.message import MessagesState
from langchain_core.messages import RemoveMessage, HumanMessage
from langgraph.prebuilt import create_react_agent


import os

from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig
from src.app.tools.analise_dados import TOOLS
from src.app.tools.faq_tools import faq_retriever
from src.app.tools.memoria import TOOLS_MEMORIA
from src.app.tools.planejamento import TOOLS_AGENDA
from src.app.memory import salvar_mensagem
from src.app.core.prompts import (
    ROUTER_PROMPT_COMPLETO,
    ANALISE_DADOS_PROMPT_COMPLETO,
    PLANEJAMENTO_PROMPT_COMPLETO,
    ORQUESTRADOR_PROMPT_COMPLETO,
    FAQ_PROMPT_COMPLETO,
)
from src.app.guardrail import guardrail_entrada, guardrail_saida, anonimizar_entrada, desanonimizar_saida, _limpar_protocolos
import re
from datetime import datetime


agora = datetime.now().strftime("%H:%M:%S")


router_app       = create_react_agent(model=llm_rapido,       tools=[],                            prompt=ROUTER_PROMPT_COMPLETO)
analise_dados_app = create_react_agent(model=llm_especialista, tools=TOOLS + TOOLS_MEMORIA,        prompt=ANALISE_DADOS_PROMPT_COMPLETO)
# Orquestrador utiliza invocação direta do modelo com prompt de sistema (sem tools)
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
def _obter_texto(msg) -> str:
    if msg is None:
        return ""
    if hasattr(msg, "text") and msg.text:
        return str(msg.text).strip()
    if hasattr(msg, "content"):
        c = msg.content
    else:
        c = msg
    if isinstance(c, str):
        return c.strip()
    if isinstance(c, list):
        partes = []
        for item in c:
            if isinstance(item, str):
                partes.append(item)
            elif isinstance(item, dict):
                if "text" in item and item["text"]:
                    partes.append(str(item["text"]))
            elif hasattr(item, "text") and item.text:
                partes.append(str(item.text))
        if partes:
            return "\n".join(partes).strip()
    return str(c).strip()

def _extrair_pergunta_protocolo(texto: str) -> str:
    if not texto:
        return ""
    match = re.search(r"PERGUNTA_ORIGINAL=\[(.*?)\]", texto, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    match_sem_colchetes = re.search(r"PERGUNTA_ORIGINAL=(.*)", texto, flags=re.DOTALL)
    if match_sem_colchetes:
        return match_sem_colchetes.group(1).strip()
    return _limpar_protocolos(texto)


def no_roteador(estado: Estado, config: RunnableConfig) -> dict:
    # Manter janela deslizante de no máximo as últimas 6 mensagens para não inflar o contexto
    mensagens_recentes = list(estado["messages"])[-6:]
    saida = router_app.invoke({"messages": mensagens_recentes}, config=config)
    texto = _obter_texto(saida["messages"][-1])

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
    entrada = estado.get("input") or ""
    pergunta = _extrair_pergunta_protocolo(entrada) or entrada
    saida = analise_dados_app.invoke(
        {"messages": [{"role": "human", "content": pergunta}]},
        config=config,
    )
    texto = _obter_texto(saida["messages"][-1])
    texto = _limpar_protocolos(texto)
    return {
        "saida_especialista": texto,
        "resposta_final":     texto,
        "agentes_chamados":   ["analise_dados"],
    }


def no_faq(estado: Estado, config: RunnableConfig) -> dict:
    entrada = estado.get("input") or ""
    pergunta = _extrair_pergunta_protocolo(entrada) or entrada
    saida = faq_app.invoke(
        {"messages": [{"role": "human", "content": pergunta}]},
        config=config,
    )
    texto = _obter_texto(saida["messages"][-1])
    texto = _limpar_protocolos(texto)
    return {
        "saida_especialista": texto,
        "resposta_final":     texto,
        "agentes_chamados":   ["faq"],
    }


def no_orquestrador(estado: Estado, config: RunnableConfig) -> dict:
    conteudo_entrada = estado.get("saida_especialista") or estado.get("input") or ""
    mensagens = [
        {"role": "system", "content": ORQUESTRADOR_PROMPT_COMPLETO},
        {"role": "human", "content": conteudo_entrada},
    ]
    resp = llm_rapido.invoke(mensagens)
    texto = _obter_texto(resp)
    texto = _limpar_protocolos(texto)
    return {
        "resposta_final":   texto,
        "agentes_chamados": ["orquestrador"],
    }



# === Quero e TENHO que estudar isso ===

def no_guardrail(estado: Estado) -> dict:
    msg_usuario = estado["messages"][-1]
    puser = _obter_texto(msg_usuario)
    anonimizado, novo_mapa = anonimizar_entrada(puser)

    resposta = guardrail_entrada(anonimizado)
    if resposta["bloqueado"]:
        return {
            "resposta_final": resposta["mensagem"],
            "agentes_chamados": ["guardrail_entrada"],
            "messages": [{"role": "system", "content": f"[GUARDRAIL BLOQUEOU] Motivo: {resposta['motivo']}"}],
        }
    else:
        msg_remover = [RemoveMessage(id=msg_usuario.id)] if hasattr(msg_usuario, "id") and msg_usuario.id else []
        return {
            "input": anonimizado,
            "mapa_pii": novo_mapa,
            "agentes_chamados": ["guardrail_entrada"],
            "messages": msg_remover + [{"role": "human", "content": anonimizado}],
        }


def no_guardrail_saida(estado: Estado) -> dict:
    resp = estado.get("resposta_final") or estado.get("saida_especialista") or ""
    resultado = guardrail_saida(resp, estado.get("mapa_pii", {}))
    return {
        "messages": [{"role": "system", "content": f"[GUARDRAIL REVISOU SAÍDA] Resultado: {resultado['motivo']}"}],
        "resposta_final": resultado["conteudo"]
    }

def roteador_guardrail_entrd(estado: Estado) -> str:
    if estado.get("resposta_final"):
        return "fim"
    return "roteador"

# === ^^^^^^^^^^ Quero e TENHO que estudar isso ^^^^^^^^^^ ===


# ==============================================================================
# FUNÇÃO DE DECISÃO
# ==============================================================================
def decidir_especialista(estado: Estado) -> str:
    """Lê o protocolo do roteador e devolve o nome do próximo nó."""
    texto = estado.get("input", "").strip()

    if not texto.startswith("ROUTE="):
        return "fim"   # resposta direta já foi escrita no nó do roteador

    rota = texto.split("\n", 1)[0].split("=", 1)[1].strip().lower()
    if rota in ("motorista", "alerta", "dashboard", "analise_dados"):
        return "analise_dados"
    # planejamento removido
    elif rota in ("faq", "duvidas"):
        return "faq"
    return "analise_dados"



# ==============================================================================
# CONSTRUÇÃO DO GRAFO
# ==============================================================================
grafo = StateGraph(Estado)

grafo.add_node("roteador",     no_roteador)
grafo.add_node("analise_dados",   no_analise_dados)
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
        "faq":        "faq",
        "fim":        END,       # resposta direta: sem especialista nem orquestrador
    },
)
grafo.add_edge("analise_dados",   "orquestrador")
grafo.add_edge("orquestrador", "guardrail_saida")
grafo.add_edge("faq",          "guardrail_saida")
grafo.add_edge("guardrail_saida", END)
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
        "messages": [HumanMessage(content=pergunta_usuario)],
        "resposta_final": "",
        "saida_especialista": "",
    }

    estado_final = fluxo_agentes.invoke(
        estado_inicial,
        config={"configurable": {"thread_id": session_id}},
    )

    resposta = estado_final.get("resposta_final") or estado_final.get("saida_especialista") or "Desculpe, não consegui processar a resposta."
    print(f"[debug] agentes chamados: {estado_final.get('agentes_chamados', [])}")
    return {
        "resposta": resposta,
        "agentes_chamados": estado_final.get("agentes_chamados", []),
    }


# ==============================================================================
# [LOOP REMOVIDO]
# ==============================================================================