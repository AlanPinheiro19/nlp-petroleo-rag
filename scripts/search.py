"""
Busca semântica via CLI — útil para testar sem abrir o Streamlit.
Uso: python scripts/search.py "query aqui" [--k 5]
"""
import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import setup_logging, format_source
from src.indexer import build_index
from src.retriever import semantic_search

setup_logging("INFO")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Busca semântica CLI")
    parser.add_argument("query", help="Texto da busca")
    parser.add_argument("--k", type=int, default=5, help="Número de resultados")
    args = parser.parse_args()

    try:
        vs = build_index()
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    results = semantic_search(vs, args.query, k=args.k)

    print(f"\n🔍 Query: '{args.query}'")
    print(f"📄 {len(results)} resultado(s) encontrado(s)\n")
    print("─" * 70)

    for i, r in enumerate(results, 1):
        sim = max(0, (1 - r.score) * 100) if r.score > 0 else (1 / (1 + r.score)) * 100
        src = format_source(r.source, r.page)
        print(f"\n#{i} [{sim:.1f}% sim] 📄 {src}")
        print(r.content[:400] + ("..." if len(r.content) > 400 else ""))
        print("─" * 70)


if __name__ == "__main__":
    main()
