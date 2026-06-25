"""
Script standalone para construir/reconstruir o índice FAISS.
Uso: python scripts/build_index.py [--force]

Exemplo:
    python scripts/build_index.py          # só reconstrói se não existir
    python scripts/build_index.py --force  # força reconstrução
"""
import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import RAW_DIR, VECTORSTORE_DIR
from src.utils import setup_logging, validate_data_dir
from src.indexer import build_index

setup_logging("INFO")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Constrói índice FAISS")
    parser.add_argument("--force", action="store_true", help="Força reconstrução")
    parser.add_argument("--data-dir", default=str(RAW_DIR), help="Diretório com documentos")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)

    if not validate_data_dir(data_dir):
        logger.error(f"Nenhum PDF ou TXT encontrado em {data_dir}")
        logger.info("Adicione documentos antes de indexar.")
        sys.exit(1)

    try:
        vs = build_index(data_dir=data_dir, force=args.force)
        logger.info(f"✅ Índice pronto em {VECTORSTORE_DIR}")
    except Exception as e:
        logger.error(f"❌ Erro ao construir índice: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
