import os, time, random
import pymysql
from datetime import datetime

DB_HOST=os.getenv("DB_HOST","98.89.79.137")
DB_USER=os.getenv("DB_USER","devops")
DB_PASS=os.getenv("DB_PASS","DevOpsPass456")
DB_NAME=os.getenv("DB_NAME","syslogs")

def ensure_table():
    conn = pymysql.connect(host=DB_HOST,user=DB_USER,password=DB_PASS,database=DB_NAME,autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("""
              CREATE TABLE IF NOT EXISTS stats (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                timestamp DATETIME NOT NULL,
                cpu_usage DOUBLE,
                memory_usage DOUBLE
              )
            """)
    finally:
        conn.close()

def write_point(cpu, mem):
    conn = pymysql.connect(host=DB_HOST,user=DB_USER,password=DB_PASS,database=DB_NAME,autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO stats (timestamp, cpu_usage, memory_usage) VALUES (NOW(), %s, %s)",
                (cpu, mem)
            )
    finally:
        conn.close()

if __name__ == "__main__":
    ensure_table()
    # one-shot write (the systemd timer runs this every 5 mins)
    cpu = random.uniform(0, 100)
    mem = random.uniform(0, 100)
    write_point(cpu, mem)