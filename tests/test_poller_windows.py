from pathlib import Path
from gpu_doctor.collector import poller

poller._run_nvidia_smi = lambda: Path('data/sample.xml').read_bytes()
poller.main(loop=False) # writes to DB once\n