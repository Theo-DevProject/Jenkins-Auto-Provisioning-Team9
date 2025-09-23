import psutil
import mysql.connector
import datetime
import os
import socket

db = mysql.connector.connect(
    host=os.getenv("DB_HOST", "localhost"),
    user=os.getenv("DB_USER", "devops"),
    password=os.getenv("DB_PASS", "password"),
    database=os.getenv("DB_NAME", "syslogs")
)

cursor = db.cursor()
cpu = psutil.cpu_percent()
mem = psutil.virtual_memory().percent
timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
host = socket.gethostname()

cursor.execute(
    "INSERT INTO stats (timestamp, cpu_usage, memory_usage, host) VALUES (%s, %s, %s, %s)",
    (timestamp, cpu, mem, host)
)
db.commit()
cursor.close()
db.close()
print(f"Logged at {timestamp} | Host: {host} | CPU: {cpu}%, MEM: {mem}%")
