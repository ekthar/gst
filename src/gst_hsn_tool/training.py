from __future__ import annotations

import csv
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable, List

from gst_hsn_tool.catalog import download_and_build_master
from gst_hsn_tool.config import (
    DEFAULT_BACKUP_FILE,
    LEARNING_DB_PATH,
    TRAINING_CORPUS_FILE,
    TRAINING_FETCH_WORKERS,
    TRAINING_GOOGLE_DISCOVERY_DELAY_SECONDS,
    TRAINING_GOOGLE_MAX_RESULTS_PER_QUERY,
    TRAINING_GOOGLE_PRODUCT_LIMIT,
    TRAINING_GOOGLE_PRODUCTS_FILE,
    TRAINING_GOOGLE_QUERIES_FILE,
    TRAINING_MAX_SECONDS,
    TRAINING_MAX_PAGES,
    TRAINING_PRACTICE_MAX_ROWS,
    TRAINING_DIR,
    TRAINING_PRACTICE_DIR,
    TRAINING_RAW_DIR,
    TRAINING_SNAPSHOT_DIR,
)
from gst_hsn_tool.loader import load_hsn_master
from gst_hsn_tool.utils import normalize_text
from gst_hsn_tool.web_collector import DEFAULT_GOOGLE_QUERIES, collect_google_search_hsn_pairs


PRODUCT_QUERY_TEMPLATES = [
    "{product} 8 digit hsn code category",
    "{product} gst hsn code 8 digit",
    "{product} hsn code with category gst",
]


def run_training_mode(
    current_master_path: Path | None = None,
    logger: Callable[[str], None] | None = None,
) -> dict:
    events = []

    def log(message: str) -> None:
        events.append(message)
        if logger:
            logger(message)

    log("Initializing training directories.")
    raw_dir = Path(TRAINING_RAW_DIR)
    snapshot_dir = Path(TRAINING_SNAPSHOT_DIR)
    practice_dir = Path(TRAINING_PRACTICE_DIR)

    raw_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    practice_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_master = snapshot_dir / f"hsn_master_snapshot_{ts}.csv"

    if current_master_path and current_master_path.exists():
        shutil.copy2(current_master_path, snapshot_master)
        source_mode = "copied_current_master"
        log(f"Snapshot created from selected master: {snapshot_master}")
    else:
        rows = download_and_build_master(snapshot_master)
        source_mode = f"downloaded_official_{rows}_rows"
        log(f"Official master downloaded and snapped with {rows} rows.")

    web_pairs_file = raw_dir / f"harvested_pairs_{ts}.csv"
    base_queries = _read_google_queries()
    product_names = _read_google_products(limit=TRAINING_GOOGLE_PRODUCT_LIMIT)
    search_queries = _compose_google_queries(base_queries, product_names)
    log(f"Starting Google-only collection with {len(search_queries)} queries.")
    web_summary = collect_google_search_hsn_pairs(
        raw_dir=raw_dir,
        output_csv=web_pairs_file,
        queries=search_queries,
        max_results_per_query=TRAINING_GOOGLE_MAX_RESULTS_PER_QUERY,
        max_pages=TRAINING_MAX_PAGES,
        max_seconds=TRAINING_MAX_SECONDS,
        max_workers=TRAINING_FETCH_WORKERS,
        discovery_request_delay=TRAINING_GOOGLE_DISCOVERY_DELAY_SECONDS,
        logger=logger,
    )
    log(
        "Google collection completed: "
        f"results={web_summary.get('google_urls_discovered', 0)}, "
        f"pages={web_summary.get('pages_visited', 0)}, pairs={web_summary.get('pair_count', 0)}"
    )
    if web_summary.get("timed_out", False):
        log("Web collection stopped by time budget; partial data retained.")

    log("Generating practice dataset from snapshot and harvested pairs.")
    practice_file, practice_rows = _build_practice_file(
        snapshot_master,
        practice_dir / f"practice_{ts}.csv",
        max_rows=TRAINING_PRACTICE_MAX_ROWS,
        harvested_pairs_csv=web_pairs_file,
    )
    log(f"Practice dataset ready: {practice_file} ({practice_rows} rows)")

    corpus_summary = _update_training_corpus(
        snapshot_master_csv=snapshot_master,
        harvested_pairs_csv=web_pairs_file,
        practice_csv=practice_file,
        corpus_csv=Path(TRAINING_CORPUS_FILE),
    )
    log(
        "Training corpus updated: "
        f"rows={corpus_summary['corpus_rows']}, size_mb={corpus_summary['corpus_size_mb']}"
    )

    return {
        "source_mode": source_mode,
        "snapshot_master": str(snapshot_master),
        "extra_downloads": len(web_summary.get("downloaded_files", [])),
        "downloaded_files": web_summary.get("downloaded_files", []),
        "google_queries_used": web_summary.get("queries_used", 0),
        "google_product_names_used": len(product_names),
        "google_urls_discovered": web_summary.get("google_urls_discovered", 0),
        "google_discovered_file": web_summary.get("google_discovered_file", ""),
        "web_pages_visited": web_summary.get("pages_visited", 0),
        "web_pairs_collected": web_summary.get("pair_count", 0),
        "web_filtered_links": web_summary.get("filtered_links", 0),
        "web_timed_out": web_summary.get("timed_out", False),
        "web_pairs_file": web_summary.get("pairs_file", ""),
        "source_status_file": web_summary.get("google_discovered_file", ""),
        "source_total": web_summary.get("google_urls_discovered", 0),
        "source_auto": web_summary.get("google_urls_discovered", 0),
        "source_restricted": 0,
        "practice_file": str(practice_file),
        "practice_rows": practice_rows,
        "corpus_file": corpus_summary["corpus_file"],
        "corpus_rows": corpus_summary["corpus_rows"],
        "corpus_size_mb": corpus_summary["corpus_size_mb"],
        "events": events,
    }


def backup_training_state(backup_zip_path: Path | None = None) -> Path:
    target = backup_zip_path or Path(DEFAULT_BACKUP_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)

    learning_file = Path(LEARNING_DB_PATH)
    training_dir = Path(TRAINING_DIR)

    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if learning_file.exists():
            zf.write(learning_file, arcname=str(learning_file).replace("\\", "/"))

        if training_dir.exists():
            for path in training_dir.rglob("*"):
                if path.is_file():
                    zf.write(path, arcname=str(path).replace("\\", "/"))

    return target


def restore_training_state(backup_zip_path: Path) -> dict:
    if not backup_zip_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_zip_path}")

    restored = 0
    with zipfile.ZipFile(backup_zip_path, "r") as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue

            member_path = Path(member.filename)
            if not _is_allowed_restore_path(member_path):
                continue

            dest = Path(member.filename)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member, "r") as src, dest.open("wb") as dst:
                dst.write(src.read())
            restored += 1

    return {
        "backup": str(backup_zip_path),
        "files_restored": restored,
    }


def _is_allowed_restore_path(path: Path) -> bool:
    text = str(path).replace("\\", "/")
    allowed_prefixes = [
        Path(LEARNING_DB_PATH).as_posix(),
        Path(TRAINING_DIR).as_posix(),
    ]
    return any(text.startswith(prefix) for prefix in allowed_prefixes)


def _read_google_queries() -> List[str]:
    queries_file = Path(TRAINING_GOOGLE_QUERIES_FILE)
    queries = []
    if queries_file.exists():
        with queries_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                q = line.strip()
                if not q or q.startswith("#"):
                    continue
                queries.append(q)
    if not queries:
        queries = DEFAULT_GOOGLE_QUERIES[:]
    return queries


def _read_google_products(limit: int = 300) -> List[str]:
    products_file = Path(TRAINING_GOOGLE_PRODUCTS_FILE)
    products = []
    if products_file.exists():
        with products_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                value = line.strip()
                if not value or value.startswith("#"):
                    continue
                products.append(value)
                if len(products) >= limit:
                    break
    return products


def _compose_google_queries(base_queries: List[str], product_names: List[str]) -> List[str]:
    seen = set()
    out = []

    for query in base_queries:
        q = query.strip()
        if not q:
            continue
        key = normalize_text(q)
        if key and key not in seen:
            seen.add(key)
            out.append(q)

    for product in product_names:
        p = product.strip()
        if not p:
            continue
        for template in PRODUCT_QUERY_TEMPLATES:
            query = template.format(product=p)
            key = normalize_text(query)
            if key and key not in seen:
                seen.add(key)
                out.append(query)

    return out


def _build_practice_file(
    master_csv: Path,
    output_csv: Path,
    max_rows: int = 5000,
    harvested_pairs_csv: Path | None = None,
) -> tuple[Path, int]:
    hsn_rows = load_hsn_master(master_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    rows_written = 0
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "practice_input",
                "target_hsn8",
                "target_hsn4",
                "target_hsn6",
                "target_description",
                "difficulty",
                "source",
            ],
        )
        writer.writeheader()

        for row in hsn_rows:
            if rows_written >= max_rows:
                break

            description = str(row.get("description", "")).strip()
            if not description:
                continue

            variants = _generate_variants(description)
            for difficulty, variant in variants:
                writer.writerow(
                    {
                        "practice_input": variant,
                        "target_hsn8": row["hsn8"],
                        "target_hsn4": row["hsn4"],
                        "target_hsn6": row["hsn6"],
                        "target_description": description,
                        "difficulty": difficulty,
                        "source": "training_mode",
                    }
                )
                rows_written += 1
                if rows_written >= max_rows:
                    break

        if harvested_pairs_csv and harvested_pairs_csv.exists() and rows_written < max_rows:
            for row in _iter_harvested_pairs(harvested_pairs_csv):
                if rows_written >= max_rows:
                    break

                code = row.get("hsn_code", "")
                if len(code) < 4:
                    continue
                hsn4 = code[:4]
                hsn6 = code[:6] if len(code) >= 6 else ""
                writer.writerow(
                    {
                        "practice_input": row.get("description", ""),
                        "target_hsn8": code if len(code) == 8 else "",
                        "target_hsn4": hsn4,
                        "target_hsn6": hsn6,
                        "target_description": row.get("description", ""),
                        "difficulty": "web",
                        "source": row.get("source", "web_collector"),
                    }
                )
                rows_written += 1

    return output_csv, rows_written


def _iter_harvested_pairs(path: Path):
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield row


def _update_training_corpus(
    snapshot_master_csv: Path,
    harvested_pairs_csv: Path,
    practice_csv: Path,
    corpus_csv: Path,
) -> dict:
    corpus_csv.parent.mkdir(parents=True, exist_ok=True)

    existing = {}
    if corpus_csv.exists():
        with corpus_csv.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                key = _corpus_key(row)
                if key:
                    existing[key] = row

    def upsert(row: dict) -> None:
        key = _corpus_key(row)
        if key:
            existing[key] = row

    # Bring in official snapshot records.
    for row in load_hsn_master(snapshot_master_csv):
        upsert(
            {
                "input_text": row.get("description", ""),
                "target_hsn8": row.get("hsn8", ""),
                "target_hsn4": row.get("hsn4", ""),
                "target_hsn6": row.get("hsn6", ""),
                "target_description": row.get("description", ""),
                "difficulty": "official",
                "source": "snapshot_master",
            }
        )

    # Bring in harvested web pairs.
    if harvested_pairs_csv.exists():
        for row in _iter_harvested_pairs(harvested_pairs_csv):
            code = str(row.get("hsn_code", "")).strip()
            if not code:
                continue
            upsert(
                {
                    "input_text": row.get("description", ""),
                    "target_hsn8": code if len(code) == 8 else "",
                    "target_hsn4": code[:4] if len(code) >= 4 else "",
                    "target_hsn6": code[:6] if len(code) >= 6 else "",
                    "target_description": row.get("description", ""),
                    "difficulty": "web",
                    "source": row.get("source", "web_collector"),
                }
            )

    # Bring in generated practice rows.
    if practice_csv.exists():
        with practice_csv.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                upsert(
                    {
                        "input_text": row.get("practice_input", ""),
                        "target_hsn8": row.get("target_hsn8", ""),
                        "target_hsn4": row.get("target_hsn4", ""),
                        "target_hsn6": row.get("target_hsn6", ""),
                        "target_description": row.get("target_description", ""),
                        "difficulty": row.get("difficulty", ""),
                        "source": row.get("source", "training_mode"),
                    }
                )

    with corpus_csv.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "input_text",
            "target_hsn8",
            "target_hsn4",
            "target_hsn6",
            "target_description",
            "difficulty",
            "source",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for _, row in sorted(existing.items(), key=lambda item: item[0]):
            writer.writerow({key: row.get(key, "") for key in fieldnames})

    size_mb = round(corpus_csv.stat().st_size / (1024 * 1024), 2)
    return {
        "corpus_file": str(corpus_csv),
        "corpus_rows": len(existing),
        "corpus_size_mb": size_mb,
    }


def _corpus_key(row: dict) -> str:
    input_text = normalize_text(str(row.get("input_text", "")).strip())
    hsn8 = str(row.get("target_hsn8", "")).strip()
    hsn6 = str(row.get("target_hsn6", "")).strip()
    hsn4 = str(row.get("target_hsn4", "")).strip()
    if not input_text:
        return ""
    return "|".join([input_text, hsn8, hsn6, hsn4])


def _generate_variants(description: str) -> List[tuple[str, str]]:
    norm = normalize_text(description)
    tokens = [t for t in norm.split() if t]
    if not tokens:
        return [("easy", norm)]

    easy = " ".join(tokens[:6])

    medium_tokens = tokens[:]
    if len(medium_tokens) > 2:
        medium_tokens = [t for i, t in enumerate(medium_tokens) if i % 3 != 1]
    medium = " ".join(medium_tokens[:6])

    hard_tokens = []
    for tok in tokens[:6]:
        if len(tok) > 4:
            hard_tokens.append(tok[:-1])
        else:
            hard_tokens.append(tok)
    hard = " ".join(hard_tokens)

    out = [("easy", easy)]
    if medium and medium != easy:
        out.append(("medium", medium))
    if hard and hard not in {easy, medium}:
        out.append(("hard", hard))
    return out
