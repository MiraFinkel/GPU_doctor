import json, sys, requests, typer
API = "http://127.0.0.1:8000/ask_gpu"

app = typer.Typer(add_completion=False)

@app.command()
def ask(text: str = typer.Argument(..., help="query or run-id")):
    payload = {"query": text} if not text.startswith("run-") else {"run_id": text}
    r = requests.post(API, json=payload, timeout=30)
    try:
        ans = r.json()
        print(json.dumps(ans, indent=2, ensure_ascii=False))
    except Exception:
        print("Error:", r.text, file=sys.stderr); sys.exit(1)

if __name__ == "__main__":
    app()          # `python -m gpu_doctor.cli_ask ask "Why high VRAM?"`
