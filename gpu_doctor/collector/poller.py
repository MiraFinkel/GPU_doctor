# collector/poller.py
from __future__ import annotations

import os
import socket
import subprocess
import time
from datetime import datetime, timezone

from lxml import etree  # pip install lxml

from . import db
import logging

# *** How to override at runtime:
# *** Faster polling, keep 14 days, prune every hour (120 loops at 30 s)
# export GPU_DOC_POLL_SEC=10
# export GPU_DOC_KEEP_DAYS=14
# export GPU_DOC_PRUNE_EVERY=360   # 10 s × 360 ≈ 1 h
# python -m collector.poller

POLL_INTERVAL = int(os.getenv("GPU_DOC_POLL_SEC", 30))
PRUNE_EVERY_N = int(os.getenv("GPU_DOC_PRUNE_EVERY", 100))
RETENTION_DAYS = int(os.getenv("GPU_DOC_KEEP_DAYS", 7))
logging.basicConfig(
    level=os.getenv("GPU_DOC_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s  %(levelname)s %(message)s",
)

POLL_INTERVAL = 30  # seconds

NVSMI_FIELDS = [
    "minor_number",
    "fb_memory_usage/used",
    "utilization/gpu_util",
    "utilization/memory_util",
    "temperature/gpu_temp",
    "power_readings/power_draw",
]
NSMI_QUERY = ",".join(NVSMI_FIELDS)


def _run_nvidia_smi() -> bytes:
    try:
        return subprocess.check_output(
            ["nvidia-smi", f"--query-gpu={NSMI_QUERY}", "--format=xml"],
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as exc:
        logging.warning("nvidia-smi failed: %s", exc.output.decode(errors="ignore"))
        raise


def _safe_int(text: str | None, default: int = 0) -> int:
    try:
        return int(text.split()[0]) if text else default
    except (ValueError, AttributeError):
        return default


def _parse_xml(xml_bytes: bytes) -> list[dict]:
    root = etree.fromstring(xml_bytes)
    rows, host, ts = [], socket.gethostname(), datetime.now(timezone.utc).isoformat()

    for idx, gpu in enumerate(root.findall(".//gpu")):
        # older XML may lack minor_number → fall back to loop index
        gpu_id = _safe_int(gpu.findtext("minor_number"), idx)

        base = {
            "ts": ts,
            "hostname": host,
            "gpu_id": gpu_id,
            "util_gpu": _safe_int(gpu.findtext("utilization/gpu_util")),
            "util_mem": _safe_int(gpu.findtext("utilization/memory_util")),
            "mem_used_mb": _safe_int(gpu.findtext("fb_memory_usage/used")),
            "temperature": _safe_int(gpu.findtext("temperature/gpu_temp")),
            "power_w": _safe_int(gpu.findtext("power_readings/power_draw")),
            "ecc_errors": 0,
            "pid": None,
            "process_name": None,
            "user": None,
            "run_tag": None,
        }
        rows.append(base)  # default snapshot when no process list
    return rows


def main(loop: bool = True) -> None:
    counter = 0
    while True:
        try:
            xml = _run_nvidia_smi()
            records = _parse_xml(xml)
            db.insert_log(records)
        except Exception as exc:
            logging.error("Collector error: %s", exc)

        # prune periodically
        counter += 1
        if counter % PRUNE_EVERY_N == 0:
            db.prune_older_than(RETENTION_DAYS)
            logging.info("DB pruned to keep last %d days", RETENTION_DAYS)

        if not loop:
            break
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    # `python -m collector.poller --once` for a single snapshot
    import argparse

    parser = argparse.ArgumentParser(description="GPU Doctor telemetry poller")
    parser.add_argument("--once", action="store_true", help="take one snapshot and exit")
    args = parser.parse_args()
    main(loop=not args.once)
