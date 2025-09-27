#!/usr/bin/env python3
import os
from flask import Flask, request, render_template_string
import pymysql

DB_HOST=os.getenv("DB_HOST","127.0.0.1")
DB_USER=os.getenv("DB_USER","devops")
DB_PASS=os.getenv("DB_PASS","DevOpsPass456")
DB_NAME=os.getenv("DB_NAME","syslogs")

app = Flask(__name__)

PAGE = """
<!doctype html><title>Read-only SQL (SELECT ... LIMIT ... only)</title>
<h1>Read-only SQL (SELECT ... LIMIT ... only)</h1>
<form method="POST">
  <textarea name="q" rows="6" cols="120">{{ q }}</textarea><br>
  <button type="submit">Run</button>
</form>
{% if err %}<pre style="color:red">{{ err }}</pre>{% endif %}
{% if rows %}
  <p>Rows: {{ rows|length }}</p>
  <table border=1 cellpadding=4 cellspacing=0>
  <tr>{% for h in headers %}<th>{{h}}</th>{% endfor %}</tr>
  {% for r in rows %}<tr>{% for v in r %}<td>{{v}}</td>{% endfor %}</tr>{% endfor %}
  </table>
{% endif %}
"""

def run_query(q):
    if not q.strip().lower().startswith("select"):
        return None, "Only SELECT is allowed."
    if " limit " not in q.lower():
        return None, "Query must include LIMIT."
    try:
        conn = pymysql.connect(host=DB_HOST,user=DB_USER,password=DB_PASS,
                               database=DB_NAME,connect_timeout=3,read_timeout=5)
        with conn.cursor() as cur:
            cur.execute(q)
            rows = cur.fetchall()
            headers = [d[0] for d in cur.description]
        conn.close()
        return (headers, rows), None
    except Exception as e:
        return None, str(e)

@app.route("/", methods=["GET","POST"])
def home():
    q = request.form.get("q","SELECT * FROM stats ORDER BY timestamp DESC LIMIT 20;")
    headers, rows = [], []
    err = None
    if request.method == "POST":
        result, err = run_query(q)
        if result:
            headers, rows = result
    return render_template_string(PAGE, q=q, headers=headers, rows=rows, err=err)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8082)
