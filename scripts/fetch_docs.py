"""
Baixa os documentos técnicos do repositório público petrobras/3W via GitHub API.

Fonte: https://github.com/petrobras/3W/tree/main/docs
Destino: data/raw/ (relativo à raiz do projeto)

Uso:
    python scripts/fetch_docs.py              # download incremental (pula arquivos ja existentes)
    python scripts/fetch_docs.py --force      # re-baixa todos os arquivos
    python scripts/fetch_docs.py --dry-run    # lista arquivos sem baixar

Variáveis de ambiente opcionais:
    GITHUB_TOKEN  — token de acesso pessoal para aumentar rate limit (60 -> 5000 req/h)
    GITHUB_REF    — branch/tag/commit de referencia (padrao: main)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import urllib.request
import urllib.error
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------

REPO_OWNER = "petrobras"
REPO_NAME  = "3W"
DOCS_PATH  = "docs"

API_BASE = "https://api.github.com"
# Timeout por requisicao (segundos)
REQUEST_TIMEOUT = 60
# Pausa entre downloads para evitar throttling (segundos)
DOWNLOAD_DELAY  = 0.5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

def _build_headers() -> dict:
    """Monta headers HTTP, incluindo token se disponivel."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "nlp-petroleo-rag/1.0",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
        logger.debug("GITHUB_TOKEN detectado — rate limit elevado para 5000 req/h")
    return headers


def list_repo_files(ref: str = "main") -> list[dict]:
    """
    Lista todos os arquivos em REPO_OWNER/REPO_NAME/DOCS_PATH.
    Retorna lista de dicts com name, size e download_url.
    """
    url = f"{API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{DOCS_PATH}?ref={ref}"
    headers = _build_headers()

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            logger.error(
                "Rate limit atingido (HTTP 403). "
                "Defina GITHUB_TOKEN para aumentar o limite para 5000 req/h."
            )
        elif exc.code == 404:
            logger.error(f"Repositorio ou diretorio nao encontrado: {url}")
        raise

    # Filtrar apenas arquivos (ignorar subdiretorios)
    files = [
        {"name": item["name"], "size": item["size"], "download_url": item["download_url"]}
        for item in data
        if item["type"] == "file"
    ]
    return files


# ---------------------------------------------------------------------------
# Download com verificacao de tamanho
# ---------------------------------------------------------------------------

def _file_is_complete(path: Path, expected_size: int) -> bool:
    """
    Verifica se o arquivo local ja esta completo.
    Considera incompleto se tamanho diferir mais de 1% do esperado (tolerancia para
    arquivos PDF com metadados variaveis) ou se o arquivo nao existir.
    """
    if not path.exists():
        return False
    actual = path.stat().st_size
    if expected_size > 0:
        ratio = abs(actual - expected_size) / expected_size
        return ratio < 0.01  # diferenca menor que 1%
    return actual > 0


def download_file(url: str, dest: Path, expected_size: int = 0) -> bool:
    """
    Baixa um arquivo de 'url' para 'dest'.
    Exibe progresso simples em stdout.
    Retorna True em caso de sucesso, False em caso de erro recuperavel.
    """
    headers = _build_headers()
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            total = int(resp.getheader("Content-Length", 0))
            downloaded = 0
            chunk_size = 65536  # 64 KB por chunk

            with open(dest, "wb") as fout:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    fout.write(chunk)
                    downloaded += len(chunk)

                    # Progresso inline
                    if total:
                        pct = downloaded / total * 100
                        mb_done = downloaded / 1_048_576
                        mb_total = total / 1_048_576
                        print(
                            f"\r    {mb_done:.1f} / {mb_total:.1f} MB  ({pct:.0f}%)",
                            end="",
                            flush=True,
                        )

        print()  # nova linha apos progresso
        return True

    except urllib.error.URLError as exc:
        print()
        logger.error(f"Falha ao baixar {url}: {exc}")
        # Remove arquivo parcial
        if dest.exists():
            dest.unlink()
        return False


# ---------------------------------------------------------------------------
# Funcao principal
# ---------------------------------------------------------------------------

def fetch_all_docs(
    dest_dir: Path,
    force: bool = False,
    dry_run: bool = False,
    ref: str = "main",
) -> None:
    """
    Baixa todos os documentos do diretorio docs/ do repositorio 3W.

    Args:
        dest_dir:  Diretorio de destino (criado automaticamente se nao existir).
        force:     Se True, re-baixa mesmo arquivos ja existentes.
        dry_run:   Se True, apenas lista os arquivos sem baixar.
        ref:       Branch/tag/commit do repositorio (padrao: main).
    """
    logger.info(f"Consultando GitHub API: {REPO_OWNER}/{REPO_NAME}/docs @ {ref}")
    files = list_repo_files(ref=ref)

    total_size_mb = sum(f["size"] for f in files) / 1_048_576
    logger.info(f"Encontrados {len(files)} documentos ({total_size_mb:.1f} MB no total)")

    if dry_run:
        print("\nLista de documentos no repositorio:")
        for i, f in enumerate(files, 1):
            mb = f["size"] / 1_048_576
            print(f"  {i:2d}. {f['name']:<60}  {mb:6.1f} MB")
        print(f"\nTotal: {len(files)} arquivos, {total_size_mb:.1f} MB")
        return

    dest_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    skipped    = 0
    failed     = 0

    for i, file_info in enumerate(files, 1):
        name          = file_info["name"]
        expected_size = file_info["size"]
        download_url  = file_info["download_url"]
        dest_path     = dest_dir / name

        prefix = f"[{i:2d}/{len(files)}]"

        if not force and _file_is_complete(dest_path, expected_size):
            logger.info(f"{prefix} Ignorado (ja existe): {name}")
            skipped += 1
            continue

        mb = expected_size / 1_048_576
        logger.info(f"{prefix} Baixando: {name}  ({mb:.1f} MB)")

        success = download_file(download_url, dest_path, expected_size)

        if success:
            downloaded += 1
        else:
            failed += 1

        if i < len(files):
            time.sleep(DOWNLOAD_DELAY)

    # Resumo final
    print()
    logger.info("=" * 50)
    logger.info(f"Concluido: {downloaded} baixados, {skipped} ignorados, {failed} falhas")
    logger.info(f"Documentos disponiveis em: {dest_dir}")

    if failed > 0:
        logger.warning(f"{failed} arquivo(s) falharam. Execute novamente para tentar de novo.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Baixa os documentos tecnicos do repositorio petrobras/3W.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-baixa todos os arquivos, mesmo os ja existentes.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Lista os arquivos disponiveis sem efetuar download.",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="Diretorio de destino (padrao: <raiz-do-projeto>/data/raw).",
    )
    parser.add_argument(
        "--ref",
        default=os.environ.get("GITHUB_REF", "main"),
        help="Branch/tag/commit do repositorio (padrao: main).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    # Determina raiz do projeto: dois niveis acima de scripts/
    project_root = Path(__file__).resolve().parent.parent
    dest_dir = args.dest or (project_root / "data" / "raw")

    fetch_all_docs(
        dest_dir=dest_dir,
        force=args.force,
        dry_run=args.dry_run,
        ref=args.ref,
    )
