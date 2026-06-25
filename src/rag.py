"""
Pipeline RAG (Retrieval-Augmented Generation).
Combina busca semântica + LLM para responder perguntas com base nos documentos.
Suporta OpenAI (API key) e Ollama (modelo local, sem custo).
"""
from __future__ import annotations
import logging
from typing import Iterator

from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_community.vectorstores import FAISS

from config import (
    LLM_PROVIDER, OPENAI_API_KEY, OPENAI_MODEL,
    OLLAMA_MODEL, OLLAMA_BASE_URL, TOP_K, TEMPERATURE,
)

logger = logging.getLogger(__name__)

# Prompt em português — instrui o LLM a citar fontes
RAG_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template="""Você é um especialista técnico em engenharia de petróleo offshore e machine learning.
Use APENAS as informações do contexto abaixo para responder. Se não souber, diga claramente.
Cite o documento fonte quando disponível.

CONTEXTO:
{context}

PERGUNTA: {question}

RESPOSTA (em português, detalhada e técnica):""",
)


def _get_llm():
    """Instancia o LLM conforme configuração (OpenAI ou Ollama)."""
    if LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY não definida. Configure no .env")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=OPENAI_MODEL,
            temperature=TEMPERATURE,
            api_key=OPENAI_API_KEY,
        )
    elif LLM_PROVIDER == "ollama":
        from langchain_community.llms import Ollama
        return Ollama(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=TEMPERATURE,
        )
    else:
        raise ValueError(f"LLM_PROVIDER inválido: {LLM_PROVIDER}. Use 'openai' ou 'ollama'")


def build_rag_chain(vectorstore: FAISS) -> RetrievalQA:
    """Constrói a chain RAG: retriever + LLM + prompt."""
    llm = _get_llm()
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": TOP_K},
    )
    chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": RAG_PROMPT},
    )
    logger.info(f"RAG chain construída: {LLM_PROVIDER}/{OLLAMA_MODEL if LLM_PROVIDER == 'ollama' else OPENAI_MODEL}")
    return chain


def answer(chain: RetrievalQA, question: str) -> dict:
    """
    Executa a query RAG e retorna resposta + fontes.
    Returns: {"result": str, "sources": list[str]}
    """
    response = chain.invoke({"query": question})
    sources = [
        doc.metadata.get("source", "desconhecido")
        for doc in response.get("source_documents", [])
    ]
    return {
        "result": response["result"],
        "sources": list(dict.fromkeys(sources)),  # deduplica mantendo ordem
    }
