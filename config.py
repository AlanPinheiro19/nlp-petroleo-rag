"""
Configurações centrais do projeto nlp-petroleo-rag.
Todas as variáveis sensíveis (API keys) são lidas de variáveis de ambiente.
"""
import os
from pathlib import Path

# Diretórios
ROOT_DIR       = Path(__file__).resolve().parent
DATA_DIR       = ROOT_DIR / "data"
RAW_DIR        = DATA_DIR / "raw"
# FAISS's C library uses fopen (ANSI) on Windows and fails on non-ASCII paths.
# Default to a path under the user home directory which is always ASCII-safe.
# Override via VECTORSTORE_DIR env var if needed.
VECTORSTORE_DIR = Path(os.getenv(
    "VECTORSTORE_DIR",
    str(Path.home() / ".petrorag" / "vectorstore"),
))

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
APP_TITLE = "PetroRAG — Busca Semantica & IA para Pocos Offshore"

# Repositorio fonte dos documentos (publico, sem autenticacao obrigatoria)
# GITHUB_TOKEN (env var) eleva o rate limit de 60 para 5000 req/h
GITHUB_REPO_OWNER = "petrobras"
GITHUB_REPO_NAME  = "3W"
GITHUB_DOCS_PATH  = "docs"
GITHUB_REF        = os.getenv("GITHUB_REF", "main")
