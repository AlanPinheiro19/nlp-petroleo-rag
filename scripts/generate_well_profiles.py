"""
Gera perfis textuais de completude de sensores para cada poco do dataset 3W.

Cada perfil descreve:
  - Identificacao do poco e classe de evento
  - Completude percentual por sensor (% de observacoes nao-nulas)
  - Ranking de pocos por cobertura geral de sensores
  - Sensores ausentes, parciais e completos

Os arquivos .txt gerados sao indexados pelo pipeline RAG, permitindo consultas como:
  "qual poco tem maior completude de sensores?"
  "quais pocos possuem dados de QGL?"
  "pocos com P-PDG completo na classe slugging severo"

Uso:
    # Lendo parquets do projeto 3W local (recomendado se ja tem o dataset)
    python scripts/generate_well_profiles.py --source local --path D:/caminho/para/3W/dataset

    # Baixando uma amostra do GitHub (sem necessidade de clonar o repo)
    python scripts/generate_well_profiles.py --source github --classes 0 2 3 8

    # Apenas os 3 primeiros pocos de cada classe (para teste rapido)
    python scripts/generate_well_profiles.py --source github --classes 0 2 3 --limit 3
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.request
import urllib.error
from io import BytesIO
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuracao dos sensores e eventos
# ---------------------------------------------------------------------------

# Sensores primarios do paper original 3W (2019)
PRIMARY_SENSORS = [
    "P-PDG",       # Pressao de fundo de poco (downhole gauge)
    "P-TPT",       # Pressao na arvore de natal (Xmas-tree)
    "T-TPT",       # Temperatura na arvore de natal
    "P-MON-CKP",   # Pressao a montante da valvula de producao (PCK)
    "P-JUS-CKP",   # Pressao a jusante da valvula de producao (PCK)
    "T-JUS-CKP",   # Temperatura a jusante da valvula de producao
    "P-JUS-CKGL",  # Pressao a jusante da valvula de gas lift
    "QGL",         # Vazao de gas lift
]

# Todos os sensores continuos do dataset
ALL_SENSORS = PRIMARY_SENSORS + [
    "P-ANULAR", "ABER-CKP", "ABER-CKGL", "T-PDG", "T-MON-CKP",
    "P-MON-CKGL", "P-MON-SDV-P", "PT-P", "QBS", "P-JUS-BS",
]

# Mapa label -> descricao de evento
EVENT_NAMES = {
    0: "Operacao Normal",
    1: "Aumento Abrupto de BSW",
    2: "Fechamento Espurio de DHSV",
    3: "Slugging Severo",
    4: "Instabilidade de Fluxo",
    5: "Perda Rapida de Produtividade",
    6: "Restricao Rapida na Valvula PCK",
    7: "Incrustacao na Valvula PCK",
    8: "Hidrato na Linha de Producao",
    9: "Hidrato na Linha de Servico",
}

GITHUB_OWNER = "petrobras"
GITHUB_REPO  = "3W"
API_BASE     = "https://api.github.com"
RAW_BASE     = "https://raw.githubusercontent.com"


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

def _headers() -> dict:
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "nlp-petroleo-rag/1.0",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _fetch_json(url: str) -> list | dict:
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def list_class_files(event_class: int) -> list[dict]:
    """Lista os arquivos parquet de uma classe no repositorio GitHub."""
    url = f"{API_BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/dataset/{event_class}"
    try:
        items = _fetch_json(url)
        return [
            {"name": i["name"], "download_url": i["download_url"], "size": i["size"]}
            for i in items
            if i["name"].endswith(".parquet") and i["name"].startswith("WELL-")
        ]
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            logger.warning(f"Classe {event_class} nao encontrada no repositorio.")
            return []
        raise


# ---------------------------------------------------------------------------
# Analise de completude
# ---------------------------------------------------------------------------

def _extract_well_id(filename: str) -> str:
    """Extrai o identificador do poco do nome do arquivo (ex: WELL-00002)."""
    # Formato: WELL-XXXXX_TIMESTAMP.parquet
    return filename.split("_")[0]


def analyze_parquet_bytes(data: bytes, filename: str, event_class: int) -> dict | None:
    """
    Analisa um arquivo parquet em memoria.
    Retorna dicionario com metricas de completude ou None em caso de erro.
    """
    try:
        import pandas as pd
    except ImportError:
        logger.error("pandas nao instalado. Execute: pip install pandas pyarrow")
        sys.exit(1)

    try:
        df = pd.read_parquet(BytesIO(data), engine="pyarrow")
    except Exception as exc:
        logger.warning(f"Falha ao ler {filename}: {exc}")
        return None

    total_obs = len(df)
    if total_obs == 0:
        return None

    # Completude por sensor (% de valores nao-nulos)
    completeness = {}
    for sensor in PRIMARY_SENSORS + [s for s in ALL_SENSORS if s not in PRIMARY_SENSORS]:
        if sensor in df.columns:
            pct = (df[sensor].notna().sum() / total_obs) * 100
            completeness[sensor] = round(pct, 1)
        else:
            completeness[sensor] = 0.0

    # Score de cobertura primaria: media dos 8 sensores principais
    primary_scores = [completeness.get(s, 0.0) for s in PRIMARY_SENSORS]
    coverage_score = round(sum(primary_scores) / len(PRIMARY_SENSORS), 1)

    # Periodo de tempo
    try:
        ts_start = str(df.index.min())[:19]
        ts_end   = str(df.index.max())[:19]
    except Exception:
        ts_start = ts_end = "desconhecido"

    # Distribuicao das classes de evento registradas
    class_distribution = {}
    if "class" in df.columns:
        counts = df["class"].value_counts().to_dict()
        class_distribution = {
            EVENT_NAMES.get(int(k), f"Classe {k}"): int(v)
            for k, v in counts.items()
            if k is not None and str(k) != "nan"
        }

    return {
        "filename": filename,
        "well_id": _extract_well_id(filename),
        "event_class": event_class,
        "event_name": EVENT_NAMES.get(event_class, f"Classe {event_class}"),
        "total_observations": total_obs,
        "period_start": ts_start,
        "period_end": ts_end,
        "completeness": completeness,
        "coverage_score": coverage_score,
        "class_distribution": class_distribution,
    }


def analyze_local_file(path: Path, event_class: int) -> dict | None:
    """Analisa um arquivo parquet local."""
    try:
        data = path.read_bytes()
        return analyze_parquet_bytes(data, path.name, event_class)
    except Exception as exc:
        logger.warning(f"Erro ao ler {path}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Geracao de texto (perfil do poco)
# ---------------------------------------------------------------------------

def render_profile(profile: dict) -> str:
    """Converte o dicionario de metricas em texto estruturado para indexacao RAG."""
    c = profile["completeness"]

    # Classificar sensores por completude
    complete  = [s for s in PRIMARY_SENSORS if c.get(s, 0) >= 90]
    partial   = [s for s in PRIMARY_SENSORS if 10 <= c.get(s, 0) < 90]
    absent    = [s for s in PRIMARY_SENSORS if c.get(s, 0) < 10]

    lines = [
        f"PERFIL DO POCO: {profile['well_id']}",
        f"Arquivo: {profile['filename']}",
        f"Tipo de Evento: {profile['event_name']} (Classe {profile['event_class']})",
        f"Total de Observacoes: {profile['total_observations']:,}",
        f"Periodo: {profile['period_start']} ate {profile['period_end']}",
        "",
        f"SCORE DE COBERTURA DE SENSORES PRIMARIOS: {profile['coverage_score']:.1f}%",
        f"({len(complete)} de {len(PRIMARY_SENSORS)} sensores com cobertura acima de 90%)",
        "",
        "COMPLETUDE POR SENSOR PRIMARIO:",
    ]

    # Descricoes dos sensores
    sensor_desc = {
        "P-PDG":     "Pressao de fundo de poco (PDG)",
        "P-TPT":     "Pressao na arvore de natal (TPT)",
        "T-TPT":     "Temperatura na arvore de natal (TPT)",
        "P-MON-CKP": "Pressao a montante da valvula de producao (PCK montante)",
        "P-JUS-CKP": "Pressao a jusante da valvula de producao (PCK jusante)",
        "T-JUS-CKP": "Temperatura a jusante da valvula de producao",
        "P-JUS-CKGL":"Pressao a jusante da valvula de gas lift (GLCK)",
        "QGL":       "Vazao de gas lift",
    }

    for sensor in PRIMARY_SENSORS:
        pct  = c.get(sensor, 0)
        desc = sensor_desc.get(sensor, sensor)
        status = "COMPLETO" if pct >= 90 else ("PARCIAL" if pct >= 10 else "AUSENTE")
        lines.append(f"  {sensor:<14} {pct:>6.1f}%  [{status}]  {desc}")

    lines += [
        "",
        "SENSORES SECUNDARIOS DISPONIVEIS:",
    ]
    secondary = {s: v for s, v in c.items() if s not in PRIMARY_SENSORS and v > 0}
    if secondary:
        for s, pct in sorted(secondary.items(), key=lambda x: -x[1]):
            lines.append(f"  {s:<20} {pct:>6.1f}%")
    else:
        lines.append("  Nenhum sensor secundario com dados.")

    if profile["class_distribution"]:
        lines += ["", "DISTRIBUICAO DE LABELS DE EVENTO:"]
        for label, count in sorted(profile["class_distribution"].items(),
                                   key=lambda x: -x[1]):
            pct = count / profile["total_observations"] * 100
            lines.append(f"  {label:<40} {count:>6,} obs ({pct:.1f}%)")

    # Resumo semantico — util para busca por linguagem natural
    lines += [
        "",
        "RESUMO SEMANTICO:",
        f"O poco {profile['well_id']} pertence ao conjunto de dados 3W da Petrobras "
        f"com instancias do tipo '{profile['event_name']}'. "
        f"Possui cobertura geral de {profile['coverage_score']:.1f}% nos sensores primarios.",
    ]

    if complete:
        lines.append(
            f"Sensores com cobertura excelente (acima de 90%): {', '.join(complete)}."
        )
    if partial:
        lines.append(
            f"Sensores com cobertura parcial (10-90%): {', '.join(partial)}."
        )
    if absent:
        lines.append(
            f"Sensores ausentes ou quase sem dados (abaixo de 10%): {', '.join(absent)}."
        )

    return "\n".join(lines)


def render_summary(profiles: list[dict]) -> str:
    """Gera um documento de ranking geral de todos os pocos processados."""
    sorted_profiles = sorted(profiles, key=lambda p: -p["coverage_score"])

    lines = [
        "RANKING DE POCOS POR COMPLETUDE DE SENSORES - DATASET 3W PETROBRAS",
        f"Total de pocos analisados: {len(profiles)}",
        "",
        f"{'Rank':<5} {'Poco':<14} {'Evento':<35} {'Score':>7}  Sensores completos (>90%)",
        "-" * 100,
    ]

    for rank, p in enumerate(sorted_profiles, 1):
        complete = [s for s in PRIMARY_SENSORS if p["completeness"].get(s, 0) >= 90]
        lines.append(
            f"{rank:<5} {p['well_id']:<14} {p['event_name']:<35} "
            f"{p['coverage_score']:>6.1f}%  {', '.join(complete) if complete else 'nenhum'}"
        )

    # Top 5 por sensor
    lines += ["", "TOP 5 POCOS POR SENSOR PRIMARIO:"]
    for sensor in PRIMARY_SENSORS:
        top = sorted(profiles, key=lambda p: -p["completeness"].get(sensor, 0))[:5]
        names = [f"{p['well_id']} ({p['completeness'].get(sensor,0):.0f}%)" for p in top]
        lines.append(f"  {sensor:<14}: {', '.join(names)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Modo GitHub: download e analise
# ---------------------------------------------------------------------------

def process_github(
    event_classes: list[int],
    dest_dir: Path,
    limit: Optional[int] = None,
) -> list[dict]:
    profiles = []

    for cls in event_classes:
        logger.info(f"Listando classe {cls} ({EVENT_NAMES.get(cls, '?')})...")
        files = list_class_files(cls)

        if not files:
            continue

        if limit:
            files = files[:limit]

        logger.info(f"  {len(files)} arquivos encontrados.")

        for i, finfo in enumerate(files, 1):
            name = finfo["name"]
            mb   = finfo["size"] / 1_048_576
            logger.info(f"  [{i}/{len(files)}] Baixando {name} ({mb:.1f} MB)...")

            try:
                data = _fetch_bytes(finfo["download_url"])
            except Exception as exc:
                logger.warning(f"  Falha: {exc}")
                continue

            profile = analyze_parquet_bytes(data, name, cls)
            if profile:
                profiles.append(profile)
                _save_profile(profile, dest_dir)
                logger.info(f"  Score: {profile['coverage_score']:.1f}%")

            time.sleep(0.3)

    return profiles


# ---------------------------------------------------------------------------
# Modo local: leitura de arquivos ja baixados
# ---------------------------------------------------------------------------

def process_local(dataset_dir: Path, dest_dir: Path) -> list[dict]:
    """
    Processa parquets de um diretorio local com estrutura:
        dataset_dir/{event_class}/WELL-XXXXX_timestamp.parquet
    """
    profiles = []

    for class_dir in sorted(dataset_dir.iterdir()):
        if not class_dir.is_dir():
            continue
        try:
            event_class = int(class_dir.name)
        except ValueError:
            continue

        parquets = sorted(class_dir.glob("WELL-*.parquet"))
        logger.info(
            f"Classe {event_class} ({EVENT_NAMES.get(event_class, '?')}): "
            f"{len(parquets)} arquivos"
        )

        for pq_path in parquets:
            profile = analyze_local_file(pq_path, event_class)
            if profile:
                profiles.append(profile)
                _save_profile(profile, dest_dir)

    return profiles


# ---------------------------------------------------------------------------
# Salvar perfil
# ---------------------------------------------------------------------------

def _save_profile(profile: dict, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = f"perfil_{profile['well_id']}_classe{profile['event_class']}.txt"
    text = render_profile(profile)
    (dest_dir / filename).write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera perfis textuais de completude de sensores para indexacao RAG.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        choices=["local", "github"],
        default="github",
        help="Fonte dos dados: 'local' (parquets ja baixados) ou 'github' (download).",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="[--source local] Caminho para o diretorio dataset/ com subdiretorios por classe.",
    )
    parser.add_argument(
        "--classes",
        type=int,
        nargs="+",
        default=[0, 2, 3, 4, 5, 8],
        help="[--source github] Classes de eventos a processar (padrao: 0 2 3 4 5 8).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="[--source github] Numero maximo de arquivos por classe (padrao: todos).",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="Diretorio de saida para os perfis .txt (padrao: <projeto>/data/raw/well_profiles).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    project_root = Path(__file__).resolve().parent.parent
    dest_dir = args.dest or (project_root / "data" / "raw" / "well_profiles")

    logger.info(f"Saida: {dest_dir}")

    if args.source == "local":
        if not args.path:
            logger.error("--path e obrigatorio quando --source=local.")
            sys.exit(1)
        if not args.path.exists():
            logger.error(f"Diretorio nao encontrado: {args.path}")
            sys.exit(1)
        profiles = process_local(args.path, dest_dir)
    else:
        profiles = process_github(args.source_classes if hasattr(args, "source_classes")
                                  else args.classes,
                                  dest_dir, limit=args.limit)

    if not profiles:
        logger.warning("Nenhum perfil gerado.")
        sys.exit(1)

    # Salvar ranking geral
    summary_text = render_summary(profiles)
    summary_path = dest_dir / "00_ranking_completude_sensores.txt"
    summary_path.write_text(summary_text, encoding="utf-8")
    logger.info(f"Ranking salvo: {summary_path}")

    logger.info(f"Concluido: {len(profiles)} perfis gerados em {dest_dir}")
    logger.info("Execute 'make index-force' para reindexar incluindo os novos perfis.")
