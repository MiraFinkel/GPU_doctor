# GPU Doctor

*A lightweight telemetry + LLM assistant that slashes VRAM waste and Out-Of-Memory crashes on shared NVIDIA GPU servers.*

---

## ✨ What it does

* Collects `nvidia-smi` / DCGM telemetry every *N* seconds and stores it in SQLite.
* Generates MiniLM embeddings of each log line for semantic search.
* Exposes a FastAPI endpoint **`POST /ask_gpu`** that retrieves the most relevant logs, feeds them to an LLM (OpenAI o3 by default) and returns a JSON diagnosis with resource recommendations.
* Optional wrapper CLI `gpu_doc run …` tags your jobs automatically so queries like “Why did **run-42** thrash?” are pinpoint-accurate.

---

## 🗂️ Repo layout

```
gpu_doctor/
│  setup.cfg              ← packaging info + console-scripts
│  README.md
│
├─ gpu_doctor/
│   ├─ api.py             ← FastAPI (ask_gpu)
│   ├─ cli.py             ← gpu_doc run …
│   └─ collector/
│        ├─ poller.py     ← telemetry daemon
│        ├─ db.py
│        ├─ embeddings.py
│        └─ retriever.py
│
├─ deploy/
│   ├─ gpu-doctor.service ← example systemd unit
│   └─ docker-compose.yaml    ← GPU-enabled container
└─ scripts/
    └─ backfill_embeddings.py
```

---

## ⚡ Quick start

### Windows workstation (no GPU required)

```powershell
git clone https://github.com/<you>/gpu_doctor.git
cd gpu_doctor
python -m venv .venv; .\.venv\Scripts\Activate
pip install -r requirements-linux.txt
pip install -e .

python -m collector.poller --once          # one snapshot → gpu_logs.db
python scripts/backfill_embeddings.py      # builds FAISS index
uvicorn gpu_doctor.api:app --port 8080     # RAG endpoint at http://localhost:8080
```

### Ubuntu 22.04 GPU server

```bash
git clone https://github.com/<you>/gpu_doctor.git && cd gpu_doctor
python3.8 -m venv .venv && source .venv/bin/activate
pip install -r requirements-linux.txt && pip install -e .

sudo cp deploy/gpu-doctor.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now gpu-doctor
```

### Docker (NVIDIA Container Runtime required)

```bash
docker compose up -d                     # API on port 8080, data in ./data
```

---

## 🔧 Common CLI

| Task               | Command                                                             |
| ------------------ | ------------------------------------------------------------------- |
| Tag & launch a job | `gpu_doc run python train.py`                                       |
| Manual snapshot    | `gpu_poll --once` *(alias for `python -m collector.poller --once`)* |
| Ask “why” via curl | `curl -X POST localhost:8080/ask_gpu -d '{"run_id":"run-42"}'`      |

---

## 🛠️ Environment knobs

| Variable            | Default     | Purpose                                         |
| ------------------- | ----------- | ----------------------------------------------- |
| `GPU_DOC_POLL_SEC`  | `30`        | Polling interval (seconds)                      |
| `GPU_DOC_KEEP_DAYS` | `7`         | Retention window for auto-prune                 |
| `GPU_DOC_TOPK`      | `8`         | How many log chunks to send to the LLM          |
| `GPU_DOC_MODEL`     | `openai:o3` | Model alias (`openai:o3`, `llama3:local`, etc.) |
| `OPENAI_API_KEY`    | —           | Required only for OpenAI endpoints              |

---

## 📈 Roadmap

* DCGM metrics (ECC, throttling) enrichment
* Slack / Teams bot wrapper
* Grafana dashboard with per-run timelines
* K8s & Slurm deployment charts

