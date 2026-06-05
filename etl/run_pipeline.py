"""
run_pipeline.py — Olist ETL orchestrator

Usage:
    python -m etl.run_pipeline
    python etl/run_pipeline.py
"""

import logging
import sys
import time
from pathlib import Path

# Make sure the project root is on sys.path when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.extract import load_raw_data
from etl.transform import transform
from etl.load import load_to_db


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(open(sys.stdout.fileno(), mode='w', encoding='utf-8', closefd=False)),
        logging.FileHandler("etl/pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("olist.pipeline")


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def run_extract() -> dict:
    logger.info("=" * 60)
    logger.info("STEP 1 — EXTRACT")
    logger.info("=" * 60)
    t0 = time.perf_counter()
    raw = load_raw_data()
    elapsed = time.perf_counter() - t0
    logger.info("Extract complete — %d tables loaded in %.1fs", len(raw), elapsed)
    return raw


def run_transform(raw: dict) -> dict:
    logger.info("=" * 60)
    logger.info("STEP 2 — TRANSFORM")
    logger.info("=" * 60)
    t0 = time.perf_counter()
    transformed = transform(raw)
    elapsed = time.perf_counter() - t0
    logger.info(
        "Transform complete — %d tables built in %.1fs",
        len(transformed), elapsed,
    )
    return transformed


def run_load(transformed: dict) -> None:
    logger.info("=" * 60)
    logger.info("STEP 3 — LOAD")
    logger.info("=" * 60)
    t0 = time.perf_counter()
    load_to_db(transformed)
    elapsed = time.perf_counter() - t0
    logger.info("Load complete in %.1fs", elapsed)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    pipeline_start = time.perf_counter()
    logger.info("Olist ETL pipeline starting …")

    try:
        raw = run_extract()
    except FileNotFoundError as exc:
        logger.error("Extract failed — CSV not found: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.exception("Extract failed with unexpected error: %s", exc)
        sys.exit(1)

    try:
        transformed = run_transform(raw)
    except Exception as exc:
        logger.exception("Transform failed: %s", exc)
        sys.exit(1)

    try:
        run_load(transformed)
    except Exception as exc:
        logger.exception("Load failed: %s", exc)
        sys.exit(1)

    total = time.perf_counter() - pipeline_start
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE — total time: %.1fs", total)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
