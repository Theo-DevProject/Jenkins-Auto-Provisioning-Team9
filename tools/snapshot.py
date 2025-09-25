# tools/snapshot.py
import os, csv
import pymysql
import matplotlib.pyplot as plt

DB_HOST = os.getenv("DB_HOST", "172.31.25.138")
DB_USER = os.getenv("DB_USER", "devops")
DB_PASS = os.getenv("DB_PASS", "DevOpsPass456")
DB_NAME = os.getenv("DB_NAME", "syslogs")
POINTS  = int(os.getenv("POINTS", "60"))

conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, autocommit=True)
with conn.cursor() as cur:
    cur.execute(f"""
        SELECT timestamp, cpu_usage, memory_usage
        FROM stats
        ORDER BY timestamp DESC
        LIMIT {POINTS}
    """)
    rows = cur.fetchall()
conn.close()

rows = rows[::-1]  # oldest -> newest
os.makedirs("artifacts", exist_ok=True)

# CSV
with open("artifacts/stats_snapshot.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["timestamp", "cpu_usage", "memory_usage"])
    for ts, cpu, mem in rows:
        w.writerow([ts, cpu, mem])

# Chart
ts  = [r[0] for r in rows]
cpu = [float(r[1]) for r in rows]
mem = [float(r[2]) for r in rows]

plt.figure()
plt.plot(ts, cpu, label="CPU %")
plt.plot(ts, mem, label="Mem %")
plt.title("System Monitor – Latest Samples")
plt.xlabel("Time")
plt.ylabel("Percent")
plt.xticks(rotation=30, ha="right")
plt.legend()
plt.tight_layout()
plt.savefig("artifacts/stats_last_hour.png")
