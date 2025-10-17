from gpu_doctor.collector import db

sample = {
    "ts": "2025-10-14T08:00:00Z",
    "hostname": "gpu01",
    "gpu_id": 0,
    "pid": 1234,
    "process_name": "python",
    "user": "mira",
    "util_gpu": 97,
    "util_mem": 88,
    "mem_used_mb": 22000,
    "ecc_errors": 0,
    "temperature": 69,
    "power_w": 240,
    "run_tag": "run-42",
}

db.insert_log([sample])
