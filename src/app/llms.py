import os
from langchain_google_genai import ChatGoogleGenerativeAI
from src.app.config import GEMINI_API_KEY

# Gemini é o principal.
llm_gemini = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=GEMINI_API_KEY,
)

# Modelo rápido — mesmo Gemini Flash (Groq API key sem acesso a modelos de chat)
llm_rapido = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=GEMINI_API_KEY,
)

llm_groq = llm_gemini          # fallback desativado — Groq sem acesso
llm_especialista = llm_gemini
llm = llm_gemini
