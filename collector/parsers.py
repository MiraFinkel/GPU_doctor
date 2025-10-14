from __future__ import annotations

import os
import platform
import shlex
import subprocess
import time
from typing import Any, Dict, List, Optional

from lxml import etree  # type: ignore

# -----------------------------
# Helpers
# -----------------------------

def _strip_units(value: Optional[str]) -> Optional[float]:
    """Extract the leading numeric portion of a string like '45 C' or '120 W'.
    Returns None if parsing fails or value is falsy.
    """
    if not value:
        return None
    s = value.strip()
    # Keep leading sign and digits/decimal point
    num = []
    dot_seen = False
    sign_seen = False
    for ch in s:
        if ch in "+-" and not sign_seen and not num:
            num.append(ch); sign_seen = True
        elif ch.isdigit():
            num.append(ch)
        elif ch == "." and not dot_seen:
            num.append(ch); dot_seen = True
        else:
            break
    try:
        return float("".join(num)) if num else None
    except ValueError:
        return None

def _txt(node: etree._Element, path: str) -> Optional[str]:
    found = node.find(path)
    return found.text.strip() if found is not None and found.text else None

# -----------------------------
# Public API
# -----------------------------

def call_nvidia_smi_xml(cmd: str = "nvidia-smi -q -x", timeout: int = 10) -> Optional[str]:
    """Run `nvidia-smi` and return the XML output as text, or None on failure."""
    try:
        proc = subprocess.run(
            shlex.split(cmd),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return None

    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    return out if out else None

def parse_nvidia_smi_xml(xml_text: str) -> List[Dict[str, Any]]:
    """Parse `nvidia-smi -q -x` XML into a list of per-GPU dicts.

    Each dict contains normalized, unit-less fields where possible.
    Missing values are represented as None.
    """
    ts_ms = int(time.time() * 1000)
    host = platform.node()

    root = etree.fromstring(xml_text.encode("utf-8"))
    # These are usually at the root
    driver_version = _txt(root, "driver_version") or _txt(root, "cuda_driver_version")  # compat
    cuda_version = _txt(root, "cuda_version")  # may be missing on some systems

    result: List[Dict[str, Any]] = []
    for idx, gpu in enumerate(root.findall("gpu")):
        # Commonly present fields
        name = _txt(gpu, "product_name") or _txt(gpu, "product_brand")
        uuid = _txt(gpu, "uuid") or _txt(gpu, "gpu_uuid")  # field name varies by version
        pstate = _txt(gpu, "pstate")

        # Utilization block
        util_gpu = _strip_units(_txt(gpu, "utilization/gpu_util"))
        util_mem = _strip_units(_txt(gpu, "utilization/memory_util"))

        # Memory block (framebuffer)
        mem_total = _strip_units(_txt(gpu, "fb_memory_usage/total"))
        mem_used = _strip_units(_txt(gpu, "fb_memory_usage/used"))
        mem_free = _strip_units(_txt(gpu, "fb_memory_usage/free"))

        # Temperature & fan
        temp = _strip_units(_txt(gpu, "temperature/gpu_temp"))
        fan = _strip_units(_txt(gpu, "fan_speed"))

        # Power
        power_draw = _strip_units(_txt(gpu, "power_readings/power_draw"))

        # Clocks
        graphics_clock = _strip_units(_txt(gpu, "clocks/graphics_clock"))
        sm_clock = _strip_units(_txt(gpu, "clocks/sm_clock"))
        mem_clock = _strip_units(_txt(gpu, "clocks/memory_clock"))

        sample = {
            "ts_ms": ts_ms,
            "host": host,
            "driver_version": driver_version,
            "cuda_version": cuda_version,
            "gpu_index": idx,
            "uuid": uuid,
            "name": name,
            "temperature_c": temp,
            "fan_speed_pct": fan,
            "utilization_gpu_pct": util_gpu,
            "utilization_mem_pct": util_mem,
            "mem_total_mib": mem_total,
            "mem_used_mib": mem_used,
            "mem_free_mib": mem_free,
            "power_draw_w": power_draw,
            "graphics_clock_mhz": graphics_clock,
            "sm_clock_mhz": sm_clock,
            "mem_clock_mhz": mem_clock,
            "pstate": pstate,
        }
        result.append(sample)

    return result

def collect_once(cmd: str = "nvidia-smi -q -x") -> List[Dict[str, Any]]:
    """Convenience: call `nvidia-smi` and parse into samples.
    Returns an empty list if `nvidia-smi` is unavailable.
    """
    xml = call_nvidia_smi_xml(cmd=cmd)
    if not xml:
        return []
    return parse_nvidia_smi_xml(xml)
