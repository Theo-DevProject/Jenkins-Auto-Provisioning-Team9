import os, csv
import pymysql
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

DB_HOST=os.getenv("DB_HOST","172.31.25.138")
DB_USER=os.getenv("DB_USER","devops")
DB_PASS=os.getenv("DB_PASS","DevOpsPass456")
DB_NAME=os.getenv("DB_NAME","syslogs")
POINTS=int(os.getenv("POINTS","120"))

out_dir="artifacts"
os.makedirs(out_dir, exist_ok=True)

conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, autocommit=True)
try:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT timestamp, cpu_usage, memory_usage
            FROM stats
            WHERE timestamp >= NOW() - INTERVAL 1 HOUR
            ORDER BY timestamp DESC
            LIMIT %s
        """, (POINTS,))
        rows = cur.fetchall()
finally:
    conn.close()

# Write CSV
csv_path = os.path.join(out_dir, "stats_snapshot.csv")
with open(csv_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["timestamp","cpu_usage","memory_usage"])
    for ts, cpu, mem in rows:
        w.writerow([ts, cpu, mem])

# Plot PNG
rows_sorted = list(reversed(rows))
times = [r[0] for r in rows_sorted]
cpu = [float(r[1] or 0) for r in rows_sorted]
mem = [float(r[2] or 0) for r in rows_sorted]

plt.figure()
plt.plot(times, cpu, label="CPU")
plt.plot(times, mem, label="Memory")
plt.title("Last Hour - CPU/Memory")
plt.xlabel("Time")
plt.ylabel("Percent")
plt.legend()
plt.tight_layout()
png_path = os.path.join(out_dir, "stats_last_hour.png")
plt.savefig(png_path)
print(f"Wrote {csv_path} and {png_path}")