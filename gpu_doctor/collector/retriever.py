# collector/retriever.py
"""
Thin retrieval layer for GPU Doctor.

• search(text, k)        → top-k log sentences by vector similarity
• search_by_tag(tag, k)  → last k rows whose run_tag matches <tag>

Automatically chooses FAISS if gpu_logs.faiss exists, otherwise pgvector.
"""

from __future__ import annotations
import json, os, sqlite3, pickle, numpy as np
from pathlib import Path
from typing import List

from .embeddings import encode, to_text, _DB

# ---------- backend autodetect ----------------------------------------
_REPO_ROOT = Path(__file__).parents[1]
_FAISS_IDX = _REPO_ROOT / "gpu_logs.faiss"
_USE_FAISS = _FAISS_IDX.exists()

if _USE_FAISS:
    import faiss
    _IDX = faiss.read_index(str(_FAISS_IDX))
    _IDS = pickle.load(open(_FAISS_IDX.with_suffix(".ids"), "rb"))
else:
    import pgvector
    with sqlite3.connect(_DB) as _conn:
        pgvector.load(_conn)                # enable extension once

# ---------- public API -------------------------------------------------
def search(query: str, k: int = 5) -> List[str]:
    """Vector similarity search (FAISS → fast, pgvector → pure SQLite)."""
    vec = encode(query)

    if _USE_FAISS:
        D, I = _IDX.search(np.expand_dims(vec.astype("float32"), 0), k)
        with sqlite3.connect(_DB) as c:
            return [
                to_text(c.execute("SELECT * FROM gpu_log WHERE id=?", (_IDS[i],)).fetchone())
                for i in I[0]
            ]

    # pgvector path
    with sqlite3.connect(_DB) as c:
        pgvector.load(c)
        rows = c.execute(
            "SELECT *, embedding <-> json(?) AS dist "
            "FROM gpu_log ORDER BY dist LIMIT ?",
            (json.dumps(vec.tolist()), k),
        ).fetchall()
        return [to_text(r) for r in rows]

def search_by_tag(tag: str, k: int = 20) -> List[str]:
    """Return the latest <k> log sentences that match run_tag=<tag>."""
    with sqlite3.connect(_DB) as c:
        rows = c.execute(
            "SELECT * FROM gpu_log WHERE run_tag=? ORDER BY ts DESC LIMIT ?", (tag, k)
        ).fetchall()
    return [to_text(r) for r in rows]
