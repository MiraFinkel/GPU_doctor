# collector/poller.py
from __future__ import annotations

import os
import socket
import subprocess
import time
from datetime import datetime, timezone

from lxml import etree  # pip install lxml

from . import db
import re, subprocess, logging

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


def _supported_fields() -> set[str]:
    """
    Parse `nvidia-smi --help-query-gpu` once and cache the set of valid fields.
    Works on old (Colab) and new driver versions.
    """
    out = subprocess.check_output(["nvidia-smi", "--help-query-gpu"], text=True, stderr=subprocess.DEVNULL)
    # lines look like "    memory.used               : GPU memory in MiB"
    return {re.split(r"\s+", ln.strip())[0] for ln in out.splitlines() if ln.startswith("    ")}

SUPPORTED = _supported_fields()

# Preferred → Legacy  (add more pairs if you hit new errors)
FIELD_MAP = {
    "fb_memory_usage/used": "memory.used",
    "utilization/gpu_util": "utilization.gpu",
    "utilization/memory_util": "utilization.memory",
    "temperature/gpu_temp": "temperature.gpu",
    "power_readings/power_draw": "power.draw",
}

def _choose(f: str) -> str | None:
    """Return first field that exists in driver; else None."""
    return f if f in SUPPORTED else FIELD_MAP.get(f) if FIELD_MAP.get(f) in SUPPORTED else None

# ----------------------------------------------------------------------
# Replace the old constant list with:
NVSMI_FIELDS = list(filter(None, map(_choose, [
    "minor_number",
    "fb_memory_usage/used",
    "utilization/gpu_util",
    "utilization/memory_util",
    "temperature/gpu_temp",
    "power_readings/power_draw",
])))
NSMI_QUERY = ",".join(NVSMI_FIELDS or ["index"])   # always at least one field
logging.info("nvidia-smi query fields: %s", NSMI_QUERY)


def _run_nvidia_smi() -> tuple[bytes, str]:
    """Return (raw_output, fmt) where fmt is 'xml' or 'csv'."""
    try:
        return (
            subprocess.check_output(
                ["nvidia-smi", f"--query-gpu={NSMI_QUERY}", "--format=xml"],
                stderr=subprocess.PIPE,
            ),
            "xml",
        )
    except subprocess.CalledProcessError:
        # fallback: CSV without units / header
        out = subprocess.check_output(
            ["nvidia-smi", f"--query-gpu={NSMI_QUERY}", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
        )
        return out, "csv"


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

def _parse_csv(text: str) -> list[dict]:
  rows, host, ts = [], socket.gethostname(), datetime.now(timezone.utc).isoformat()
  for idx, line in enumerate(text.strip().splitlines()):
      cols = [int(x) if x.isdigit() else None for x in line.split(", ")]
      # map cols → util_gpu, util_mem, mem_used_mb, temperature, power_w
      util_gpu, util_mem, mem_used, temp, power = (cols + [None]*5)[:5]
      rows.append({
          "ts": ts, "hostname": host, "gpu_id": idx,
          "util_gpu": util_gpu, "util_mem": util_mem,
          "mem_used_mb": mem_used, "temperature": temp,
          "power_w": power, "ecc_errors": 0,
          "pid": None, "process_name": None, "user": None, "run_tag": None,
      })
  return rows


def main(loop: bool = True) -> None:
    counter = 0
    while True:
        try:
            raw, fmt = _run_nvidia_smi()
            if fmt == "xml":
                records = _parse_xml(raw)
            else:                       # CSV path
                records = _parse_csv(raw.decode())
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
