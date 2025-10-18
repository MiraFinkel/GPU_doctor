# collector/embeddings.py
from __future__ import annotations
import json, sqlite3, numpy as np
from sentence_transformers import SentenceTransformer, util
from pathlib import Path

_MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
_DB = Path(__file__).parents[1] / "gpu_logs.db"
_FAISS_IDX = Path(__file__).parents[1] / "gpu_logs.faiss"


def to_text(row: sqlite3.Row) -> str:
    """≈200-char summary used as RAG chunk."""
    return (
        f"{row['ts']} host={row['hostname']} gpu={row['gpu_id']} "
        f"util={row['util_gpu']}% mem={row['mem_used_mb']}MB "
        f"pid={row['pid']} user={row['user']} tag={row['run_tag'] or 'None'}"
    )


def encode(text: str) -> np.ndarray:
    return _MODEL.encode(text, normalize_embeddings=True)


# ---- Option A  pgvector-sqlite ---------------------------------------
def migrate_pgvector() -> None:
    """Add a VECTOR(384) column once, then back-fill."""
    with sqlite3.connect(_DB) as conn:
        conn.enable_load_extension(True)
        conn.load_extension("vector0")  # pip install pgvector-sqlite
        conn.execute("ALTER TABLE gpu_log ADD COLUMN embedding VECTOR")  # idempotent
        rows = conn.execute("SELECT id, * FROM gpu_log WHERE embedding IS NULL").fetchall()
        for r in rows:
            conn.execute(
                "UPDATE gpu_log SET embedding = ? WHERE id = ?",
                (json.dumps(encode(to_text(r)).tolist()), r["id"]),
            )
        conn.commit()

# # ---- Option B  FAISS -------------------------------------------------
import faiss, pickle
def build_faiss() -> None:
    with sqlite3.connect(_DB) as conn:
        conn.row_factory = sqlite3.Row  # <-- add this line
        rows = conn.execute("SELECT id, * FROM gpu_log").fetchall()
    vectors = np.stack([encode(to_text(r)) for r in rows])
    idx = faiss.IndexFlatIP(vectors.shape[1])
    idx.add(vectors.astype("float32"))
    faiss.write_index(idx, str(_FAISS_IDX))
    pickle.dump([r["id"] for r in rows], open(_FAISS_IDX.with_suffix(".ids"), "wb"))
