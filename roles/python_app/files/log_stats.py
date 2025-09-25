#!/usr/bin/env python3
import os, time
from datetime import datetime
import psutil, pymysql

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_USER = os.getenv("DB_USER", "devops")
DB_PASS = os.getenv("DB_PASS", "DevOpsPass456")
DB_NAME = os.getenv("DB_NAME", "syslogs")

def main():
  cpu = psutil.cpu_percent(interval=1)
  mem = psutil.virtual_memory().percent
  ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
  for _ in range(5):
    try:
      conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, autocommit=True, connect_timeout=5)
      with conn.cursor() as cur:
        cur.execute("INSERT INTO stats (timestamp, cpu_usage, memory_usage) VALUES (%s,%s,%s)", (ts, cpu, mem))
      conn.close()
      break
    except Exception:
      time.sleep(2)

if __name__ == "__main__":
  main()
