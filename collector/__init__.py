"""gpu_doctor.collector
Lightweight GPU metrics collector.

Modules
-------
poller : core loop that calls `nvidia-smi`, parses XML, and writes to SQLite
parsers: helpers to turn `nvidia-smi -q -x` XML into Python dicts
db     : tiny SQLite helpers (schema + inserts + simple queries)
"""

__all__ = ["poller", "parsers", "db"]
