import os
from app.config import GEMINI_API_KEY
from langchain.tools import tool
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

from langchain_google_genai import GoogleGenerativeAIEmbeddings


MD_PATH = os.getenv("FAQ", "FAQ.md")
# Substituição do PyPDFLoader pelo TextLoader para leitura do .md
loader = TextLoader(MD_PATH, encoding='utf-8') 
docs = loader.load()

@tool
def faq_retriever(query: str) -> str:
    """Busca informações no documento de FAQ (MD) para responder a dúvidas do usuário sobre o sistema e suas especificações."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=150)
    chunks = splitter.split_documents(docs)

    embeddings = GoogleGenerativeAIEmbeddings(
        model="embedding-2-preview",
        google_api_key=GEMINI_API_KEY,
    )

    db = FAISS.from_documents(chunks, embeddings)
    results = db.similarity_search(query, k=6)
    
    # Retornando os resultados formatados (como string) para a tool
    return "\n\n".join([doc.page_content for doc in results])