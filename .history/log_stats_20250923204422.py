import psutil
import mysql.connector
import datetime
import os

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

cursor.execute("INSERT INTO stats (timestamp, cpu_usage, memory_usage) VALUES (%s, %s, %s)",
               (timestamp, cpu, mem))
db.commit()
cursor.close()
db.close()
print(f"Logged at {timestamp} | CPU: {cpu}%, MEM: {mem}%")
