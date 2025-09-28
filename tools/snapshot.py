import os, csv, pymysql
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

conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS,
                       database=DB_NAME, autocommit=True, connect_timeout=5)
with conn.cursor() as cur:
    cur.execute("""
        SELECT timestamp, cpu_usage, memory_usage
        FROM stats
        WHERE timestamp >= NOW() - INTERVAL 1 DAY
        ORDER BY timestamp DESC
        LIMIT %s
    """, (POINTS,))
    data = cur.fetchall()
conn.close()

rows = list(reversed(data))  # oldest -> newest
csv_path = os.path.join(out_dir, "stats_snapshot.csv")
with open(csv_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["timestamp","cpu_usage","memory_usage"])
    w.writerows(rows)

# simple last-hour plot
last_hr = [r for r in rows if r[0] >= datetime.utcnow() - timedelta(hours=1)]
if not last_hr: last_hr = rows
ts = [r[0] for r in last_hr]
cpu = [r[1] for r in last_hr]
mem = [r[2] for r in last_hr]

plt.figure()
plt.plot(ts, cpu, label="CPU %")
plt.plot(ts, mem, label="Mem %")
plt.legend()
plt.xlabel("Time (UTC)")
plt.ylabel("Percent")
plt.title("System metrics (last hour)")
plt.xticks(rotation=30, ha="right")
plt.tight_layout()
png_path = os.path.join(out_dir, "stats_last_hour.png")
plt.savefig(png_path)

print(f"Wrote {csv_path} and {png_path}")
