import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from src.app.config import GEMINI_API_KEY, GROQ_API_KEY

_MODEL_RAPIDO = os.getenv("GEMINI_MODEL_RAPIDO", os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"))
_MODEL_ESPECIALISTA = os.getenv("GEMINI_MODEL_ESPECIALISTA", os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"))
_MODEL_GROQ = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Modelo rápido para guardrails, roteador e orquestrador
llm_rapido = ChatGoogleGenerativeAI(
    model=_MODEL_RAPIDO,
    google_api_key=GEMINI_API_KEY,
    temperature=0.1,
    max_retries=2,
)

# Modelo especialista para análise de dados e planejamento
llm_especialista = ChatGoogleGenerativeAI(
    model=_MODEL_ESPECIALISTA,
    google_api_key=GEMINI_API_KEY,
    temperature=0.2,
    max_retries=2,
)

# Modelo Groq (como fallback)
llm_groq = ChatGroq(
    model=_MODEL_GROQ,
    api_key=GROQ_API_KEY,
    temperature=0.1,
)

# Definição dos fallbacks
llm_rapido_com_fallback = llm_rapido.with_fallbacks([llm_groq])
llm_especialista_com_fallback = llm_especialista.with_fallbacks([llm_groq])

# llm_gemini será o especialista, llm_groq será o backup para rápido
llm_gemini = llm_especialista_com_fallback
llm = llm_rapido_com_fallback
