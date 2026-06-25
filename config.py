"""
Configurações centrais do projeto nlp-petroleo-rag.
Todas as variáveis sensíveis (API keys) são lidas de variáveis de ambiente.
"""
import os
from pathlib import Path

# Diretórios
ROOT_DIR       = Path(__file__).parent
DATA_DIR       = ROOT_DIR / "data"
RAW_DIR        = DATA_DIR / "raw"
VECTORSTORE_DIR = DATA_DIR / "vectorstore"

# Embedding model (HuggingFace — sem custo, roda local)
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # multilíngue PT/EN
)

# Chunking
CHUNK_SIZE    = int(os.getenv("CHUNK_SIZE", "512"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "64"))

# FAISS index name
FAISS_INDEX_NAME = os.getenv("FAISS_INDEX_NAME", "oilgas_index")

# LLM (OpenAI ou Ollama local)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")   # "openai" | "ollama"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OLLAMA_MODEL   = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# RAG
TOP_K = int(os.getenv("TOP_K", "5"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))

# Streamlit
APP_TITLE = "🛢️ PetroRAG — Busca Semântica & IA para Poços Offshore"
