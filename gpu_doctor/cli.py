#!/usr/bin/env python
"""
gpu_doc run <command …>

Example:
    gpu_doc run python train.py --epochs 5
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from typing import List


def _derive_tag() -> str:
    """Pick tag from scheduler or generate UUID."""
    # Slurm
    if slurm_id := os.getenv("SLURM_JOB_ID"):
        return f"slurm-{slurm_id}"
    # Kubernetes downward-API
    if pod := os.getenv("HOSTNAME"):  # in K8s, HOSTNAME = pod name
        return f"pod-{pod}"
    # Fallback
    return f"run-{uuid.uuid4().hex[:8]}"


def main(argv: List[str] | None = None) -> None:
    argv = argv or sys.argv[1:]
    if not argv or argv[0] != "run":
        print("Usage: gpu_doc run <command …>", file=sys.stderr)
        sys.exit(1)

    cmd = argv[1:]
    tag = _derive_tag()
    env = os.environ.copy()
    env["GPU_DOC_RUN_TAG"] = tag

    print(f"[gpu_doc] Tag = {tag}")
    print(f"[gpu_doc] Exec → {' '.join(cmd)}")
    # Replace current process → child keeps same PID lineage
    os.execvpe(cmd[0], cmd, env)


if __name__ == "__main__":
    main()
