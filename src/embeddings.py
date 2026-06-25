"""
Carregamento e cache do modelo de embeddings.
Usa sentence-transformers com suporte multilíngue (PT + EN).
"""
from __future__ import annotations
import logging
from functools import lru_cache
from langchain_huggingface import HuggingFaceEmbeddings
from config import EMBEDDING_MODEL

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """Retorna instância cached do modelo de embeddings."""
    logger.info(f"Carregando modelo de embeddings: {EMBEDDING_MODEL}")
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
