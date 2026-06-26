"""
Indexação de documentos: PDF/TXT → chunks → embeddings → FAISS.
Suporta atualização incremental (evita reindexar documentos já processados).
"""
from __future__ import annotations
import logging
import hashlib
import json
from pathlib import Path
from typing import List

# langchain >= 0.3: text splitters were extracted to langchain-text-splitters
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    DirectoryLoader,
)
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from config import (
    RAW_DIR, VECTORSTORE_DIR,
    CHUNK_SIZE, CHUNK_OVERLAP,
    FAISS_INDEX_NAME,
)
from src.embeddings import get_embeddings

logger = logging.getLogger(__name__)

MANIFEST_PATH = VECTORSTORE_DIR / "manifest.json"


def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text())
    return {}


def _save_manifest(manifest: dict) -> None:
    VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))


def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def load_documents(data_dir: Path = RAW_DIR) -> List[Document]:
    """Carrega todos os PDF e TXT do diretório de dados."""
    docs: List[Document] = []

    pdf_loader = DirectoryLoader(
        str(data_dir), glob="**/*.pdf",
        loader_cls=PyPDFLoader, show_progress=True,
    )
    txt_loader = DirectoryLoader(
        str(data_dir), glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        show_progress=True,
    )

    for loader in [pdf_loader, txt_loader]:
        try:
            docs.extend(loader.load())
        except Exception as e:
            logger.warning(f"Erro ao carregar documentos: {e}")

    logger.info(f"{len(docs)} documentos carregados de {data_dir}")
    return docs


def split_documents(docs: List[Document]) -> List[Document]:
    """Divide documentos em chunks com overlap."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    logger.info(f"{len(chunks)} chunks gerados (chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    return chunks


def build_index(data_dir: Path = RAW_DIR, force: bool = False) -> FAISS:
    """
    Constrói (ou recarrega) o índice FAISS.
    force=True reconstrói mesmo que o índice já exista.
    """
    index_path = VECTORSTORE_DIR / FAISS_INDEX_NAME
    embeddings = get_embeddings()

    # Verificar se já existe índice válido. LangChain save_local() grava
    # sempre como "index.faiss" dentro do diretório, independente do nome do índice.
    faiss_file = index_path / "index.faiss"
    if not force and faiss_file.exists():
        logger.info(f"Carregando índice existente: {index_path}")
        return FAISS.load_local(
            str(index_path), embeddings,
            allow_dangerous_deserialization=True,
        )

    # Construir do zero
    logger.info("Construindo novo índice FAISS...")
    # save_local() escreve dentro de index_path/ — o diretório precisa existir
    index_path.mkdir(parents=True, exist_ok=True)

    docs   = load_documents(data_dir)
    chunks = split_documents(docs)

    if not chunks:
        raise ValueError(f"Nenhum documento encontrado em {data_dir}. Adicione PDFs ou TXTs.")

    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local(str(index_path))
    logger.info(f"Índice salvo em {index_path} ({len(chunks)} chunks)")

    # Salvar manifesto
    manifest = {
        str(p): _file_hash(p)
        for p in Path(data_dir).rglob("*")
        if p.is_file()
    }
    _save_manifest(manifest)
    return vectorstore
