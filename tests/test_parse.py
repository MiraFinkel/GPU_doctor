# tests/test_parse.py
from pathlib import Path
from gpu_doctor.collector import parse_xml   # if you moved the function
xml = Path("tests/data/gpu_snapshot.xml").read_bytes()
records = parse_xml(xml)
assert records and "gpu_id" in records[0]
