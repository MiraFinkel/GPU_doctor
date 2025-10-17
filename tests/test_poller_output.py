from gpu_doctor.collector import db
import pandas as pd

with db.get_conn() as conn:
    print("Rows:", conn.execute("SELECT COUNT(*) FROM gpu_log").fetchone()[0])
    df = pd.read_sql("SELECT * FROM gpu_log ORDER BY ts DESC LIMIT 5", conn)
print(df.head())
