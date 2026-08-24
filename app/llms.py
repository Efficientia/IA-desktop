import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from app.config import GEMINI_API_KEY, GROQ_API_KEY

# Gemini é o principal.
llm_gemini = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.4,
    top_p=0.95,
    google_api_key=GEMINI_API_KEY,
)

# Caso esteja indisponível, utiliza o Groq.
llm_groq = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.4,
    top_p=0.95,
    api_key=GROQ_API_KEY,
)

llm_rapido = ChatGroq(
    model="qwen/qwen3-32b",
    temperature=0.5,
    top_p=0.95,
    api_key=GROQ_API_KEY,
)

llm_especialista = llm_gemini.with_fallbacks([llm_groq])

llm = llm_gemini.with_fallbacks([llm_groq])
