#!/usr/bin/env python3
import os
import io
import pymysql
from flask import Flask, request, send_file, render_template_string
import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_USER = os.getenv("DB_USER", "devops")
DB_PASS = os.getenv("DB_PASS", "DevOpsPass456")
DB_NAME = os.getenv("DB_NAME", "syslogs")

app = Flask(__name__)

PAGE = """
<!doctype html>
<title>Read-only SQL (SELECT ... LIMIT ... only)</title>
<h1>Read-only SQL (SELECT ... LIMIT ... only)</h1>
<form method="POST">
  <textarea name="q" rows="6" cols="120">{{ q }}</textarea><br/>
  <button type="submit">Run</button>
</form>
<p>Rows: {{ rows|length }}</p>
{{ table|safe }}

<h2>Charts</h2>
<p>Last hour (line): <img src="/chart/line?points=120" style="max-width:700px;"/></p>
<p>Latest point (pie): <img src="/chart/pie" style="max-width:400px;"/></p>
"""

def _conn():
    return pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, autocommit=True
    )

@app.route("/", methods=["GET", "POST"])
def index():
    q = request.form.get("q", "SELECT * FROM stats ORDER BY timestamp DESC LIMIT 20;")
    rows, cols, html = [], [], ""
    try:
        with _conn().cursor() as cur:
            cur.execute(q)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description] if cur.description else []
    except Exception as e:
        html = f"<pre style='color:red'>{e}</pre>"

    if rows and cols:
        # very simple HTML table
        th = "".join(f"<th>{c}</th>" for c in cols)
        trs = []
        for r in rows:
            tds = "".join(f"<td>{str(v)}</td>" for v in r)
            trs.append(f"<tr>{tds}</tr>")
        html = f"<table border=1 cellpadding=4 cellspacing=0><tr>{th}</tr>{''.join(trs)}</table>"

    return render_template_string(PAGE, q=q, rows=rows, table=html)

@app.get("/chart/line")
def chart_line():
    points = int(request.args.get("points", "120"))
    with _conn().cursor() as cur:
        cur.execute("""
            SELECT timestamp, cpu_usage, memory_usage
            FROM stats
            WHERE timestamp >= NOW() - INTERVAL 1 HOUR
            ORDER BY timestamp ASC
            LIMIT %s
        """, (points,))
        data = cur.fetchall()

    ts = [r[0] for r in data]
    cpu = [r[1] for r in data]
    mem = [r[2] for r in data]

    fig = plt.figure(figsize=(8, 3))
    plt.plot(ts, cpu, label="CPU %")
    plt.plot(ts, mem, label="Memory %")
    plt.legend()
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

@app.get("/chart/pie")
def chart_pie():
    with _conn().cursor() as cur:
        cur.execute("""
            SELECT cpu_usage, memory_usage
            FROM stats
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        row = cur.fetchone() or (0, 0)
    cpu, mem = row

    fig = plt.figure(figsize=(3.5, 3.5))
    plt.pie([cpu, mem], labels=["CPU %", "Memory %"], autopct="%1.1f%%", startangle=140)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8082)
