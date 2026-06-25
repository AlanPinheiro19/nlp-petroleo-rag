"""
Busca semântica sobre o índice FAISS.
Retorna os top-K chunks mais similares à query.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import List

from langchain_community.vectorstores import FAISS
from langchain.schema import Document

from config import TOP_K

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    content: str
    source: str
    page: int | None
    score: float


def semantic_search(
    vectorstore: FAISS,
    query: str,
    k: int = TOP_K,
) -> List[SearchResult]:
    """
    Busca semântica: retorna os k chunks mais relevantes para a query.
    Usa similaridade de cosseno entre embeddings.
    """
    docs_and_scores: list[tuple[Document, float]] = (
        vectorstore.similarity_search_with_score(query, k=k)
    )

    results = []
    for doc, score in docs_and_scores:
        results.append(SearchResult(
            content=doc.page_content,
            source=doc.metadata.get("source", "desconhecido"),
            page=doc.metadata.get("page"),
            score=float(score),
        ))

    logger.debug(f"Query: '{query[:60]}...' → {len(results)} resultados")
    return results
