# collector/poller.py
from __future__ import annotations

import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import psutil
from lxml import etree  # pip install lxml

from . import db

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
    return subprocess.check_output(
        ["nvidia-smi", f"--query-gpu={NSMI_QUERY}", "--format=xml"], stderr=subprocess.DEVNULL
    )


def _parse_xml(xml_bytes: bytes) -> List[Dict]:
    root = etree.fromstring(xml_bytes)
    rows: List[Dict] = []
    ts = datetime.now(timezone.utc).isoformat()
    host = socket.gethostname()

    for gpu in root.findall(".//gpu"):
        gpu_id = int(gpu.findtext("minor_number"))
        # Flatten per-GPU metrics (good even if no processes are running)
        gpu_base = {
            "ts": ts,
            "hostname": host,
            "gpu_id": gpu_id,
            "util_gpu": int(gpu.findtext("utilization/gpu_util").split()[0]),
            "util_mem": int(gpu.findtext("utilization/memory_util").split()[0]),
            "mem_used_mb": int(gpu.findtext("fb_memory_usage/used").split()[0]),
            "temperature": int(gpu.findtext("temperature/gpu_temp").split()[0]),
            "power_w": int(gpu.findtext("power_readings/power_draw").split()[0]),
            "ecc_errors": 0,           # placeholder (DCGM can fill later)
            "pid": None,
            "process_name": None,
            "user": None,
            "run_tag": None,
        }

        # Per-process details (if any)
        procs = gpu.findall(".//process_info")
        if not procs:
            rows.append(gpu_base)  # idle GPU snapshot
            continue

        for p in procs:
            rec = gpu_base.copy()
            pid = int(p.findtext("pid"))
            rec["pid"] = pid
            try:
                proc = psutil.Process(pid)
                rec["process_name"] = proc.name()
                rec["user"] = proc.username()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                rec["process_name"] = rec["user"] = "unknown"
            rec["run_tag"] = proc.environ().get("GPU_DOC_RUN_TAG") if proc else None
            rows.append(rec)
    return rows


def main(loop: bool = True) -> None:
    """Continuously poll nvidia-smi and write to SQLite."""
    while True:
        try:
            xml = _run_nvidia_smi()
            records = _parse_xml(xml)
            db.insert_log(records)
        except subprocess.CalledProcessError as exc:
            print(f"[WARN] nvidia-smi failed: {exc}")
        except Exception as exc:
            print(f"[ERROR] unexpected: {exc}")

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
