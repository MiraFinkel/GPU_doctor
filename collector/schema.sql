CREATE TABLE gpu_log (
  id           INTEGER PRIMARY KEY,
  ts           DATETIME NOT NULL,          -- UTC
  hostname     TEXT    NOT NULL,
  gpu_id       INTEGER NOT NULL,
  pid          INTEGER,
  process_name TEXT,
  user         TEXT,
  util_gpu     INTEGER,   -- %
  util_mem     INTEGER,   -- %
  mem_used_mb  INTEGER,
  ecc_errors   INTEGER,
  temperature  INTEGER,   -- °C
  power_w      INTEGER,
  run_tag      TEXT       -- optional job/run ID
);
CREATE INDEX idx_ts_gpu   ON gpu_log(ts, gpu_id);
CREATE INDEX idx_run_tag  ON gpu_log(run_tag);
