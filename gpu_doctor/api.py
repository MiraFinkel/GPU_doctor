# gpu_doctor/api.py
from __future__ import annotations

import os, json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

import openai

from gpu_doctor.collector import retriever

openai.api_key = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("GPU_DOC_MODEL", "openai:o3")
K = int(os.getenv("GPU_DOC_TOPK", 8))

# ---------- I/O schema -------------------------------------------------
class AskRequest(BaseModel):
    query: str | None = None
    run_id: str | None = None

class AskResponse(BaseModel):
    answer: str
    recommended_gpu_mem_mb: int | None = None
    recommended_cpu_cores: int | None = None
    flagged_anomalies: List[str] | None = None

# ---------- Prompt template -------------------------------------------
SYSTEM = """You are GPU Doctor, an expert on NVIDIA GPU telemetry.
Given recent log lines, explain the issue and recommend resources."""
TEMPLATE = """\
LOGS:
{logs}

QUESTION:
{question}

INSTRUCTIONS:
1. Diagnose root cause.
2. Suggest GPU VRAM, CPU cores, and other tuning in JSON:
   {{
     "answer": "...concise reasoning...",
     "recommended_gpu_mem_mb": <int or null>,
     "recommended_cpu_cores": <int or null>,
     "flagged_anomalies": [<strings>] }}
"""

# ---------- FastAPI ----------------------------------------------------
app = FastAPI(title="GPU Doctor RAG API")

def _retrieve_ctx(q: str, run_id: str | None) -> List[str]:
    if run_id:
        q = f"Why did run {run_id} fail?"
        # force recall logs by tag
        return retriever.search_by_tag(run_id, k=K)
    return retriever.search(q, k=K)            # vector similarity

def _llm_chat(prompt: str) -> str:
    if MODEL.startswith("openai:"):
        model = MODEL.split(":", 1)[1]
        resp = openai.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.2,
        )
        return resp.choices[0].message.content
    raise ValueError("Unsupported MODEL")

@app.post("/ask_gpu", response_model=AskResponse)
def ask_gpu(req: AskRequest):
    if not (req.query or req.run_id):
        raise HTTPException(400, "query or run_id required")

    logs = _retrieve_ctx(req.query or "", req.run_id)
    prompt = TEMPLATE.format(logs="\n".join(logs), question=req.query or f"run {req.run_id}")
    try:
        raw = _llm_chat(prompt)
        data = json.loads(raw) if raw.strip().startswith("{") else {"answer": raw}
    except Exception as exc:
        raise HTTPException(500, f"LLM failure: {exc}")

    return AskResponse(**data)
