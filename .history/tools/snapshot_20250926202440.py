import os, csv, datetime as dt
import pymysql
import matplotlib.pyplot as plt

DB_HOST=os.getenv("DB_HOST","98.89.79.137")
DB_USER=os.getenv("DB_USER","devops")
DB_PASS=os.getenv("DB_PASS","DevOpsPass456")
DB_NAME=os.getenv("DB_NAME","syslogs")
POINTS=int(os.getenv("POINTS","120"))

out_dir="artifacts"
os.makedirs(out_dir, exist_ok=True)

conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, autocommit=True)
rows=[]
with conn.cursor() as cur:
    cur.execute(f"SELECT timestamp, cpu_usage, memory_usage FROM stats ORDER BY timestamp DESC LIMIT {POINTS}")
    rows = cur.fetchall()
conn.close()

# write CSV (newest first as queried)
csv_path = os.path.join(out_dir, "stats_snapshot.csv")
with open(csv_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["timestamp","cpu_usage","memory_usage"])
    for r in rows:
        w.writerow(r)

# simple line chart (reverse to oldest->newest for nicer x-axis)
ts = [r[0] for r in rows][::-1]
cpu = [float(r[1]) for r in rows][::-1]
mem = [float(r[2]) for r in rows][::-1]

plt.figure()
plt.plot(ts, cpu, label="CPU")
plt.plot(ts, mem, label="Memory")
plt.title("Last Hour CPU/Memory")
plt.xlabel("Time")
plt.ylabel("Usage")
plt.legend()
plt.xticks(rotation=30, ha="right")
plt.tight_layout()
png_path = os.path.join(out_dir, "stats_last_hour.png")
plt.savefig(png_path)
print(f"Wrote {csv_path} and {png_path}")