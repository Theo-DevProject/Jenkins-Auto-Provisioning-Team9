import os, csv, time
import pymysql
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

DB_HOST=os.getenv("DB_HOST","98.89.79.137")
DB_USER=os.getenv("DB_USER","devops")
DB_PASS=os.getenv("DB_PASS","DevOpsPass456")
DB_NAME=os.getenv("DB_NAME","syslogs")
POINTS=int(os.getenv("POINTS","120"))

OUT_DIR="artifacts"
CSV_PATH=os.path.join(OUT_DIR,"stats_snapshot.csv")
PNG_PATH=os.path.join(OUT_DIR,"stats_last_hour.png")

os.makedirs(OUT_DIR, exist_ok=True)

def fetch():
    conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, timestamp, cpu_usage, memory_usage
                FROM stats
                ORDER BY timestamp DESC
                LIMIT %s
            """, (POINTS,))
            rows = cur.fetchall()
    finally:
        conn.close()
    return rows

def write_csv(rows):
    with open(CSV_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id","timestamp","cpu_usage","memory_usage"])
        for r in rows:
            w.writerow(r)

def plot(rows):
    # rows newest-first; reverse for time order
    rows = list(rows)[::-1]
    ts = [r[1] for r in rows]
    cpu = [float(r[2]) if r[2] is not None else 0.0 for r in rows]
    mem = [float(r[3]) if r[3] is not None else 0.0 for r in rows]

    plt.figure()
    plt.plot(ts, cpu, label="CPU")
    plt.plot(ts, mem, label="Memory")
    plt.title("Last ~hour System Stats")
    plt.xlabel("Time")
    plt.ylabel("Usage")
    plt.legend()
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(PNG_PATH)
    plt.close()

def main():
    rows = fetch()
    write_csv(rows)
    if rows:
        plot(rows)

if __name__ == "__main__":
    main()