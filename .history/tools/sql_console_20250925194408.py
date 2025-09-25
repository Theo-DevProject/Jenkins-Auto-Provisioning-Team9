from flask import Flask, request, render_template_string, send_file
import pymysql, os, io
import matplotlib.pyplot as plt

DB_HOST=os.getenv("DB_HOST","172.31.25.138")
DB_USER=os.getenv("DB_USER","devops")
DB_PASS=os.getenv("DB_PASS","DevOpsPass456")
DB_NAME=os.getenv("DB_NAME","syslogs")

TPL="""
<!doctype html><title>Syslogs SQL Console</title>
<h2>Read-only SQL (SELECT ... LIMIT ... only)</h2>
<form method="post">
  <textarea name="q" rows="6" cols="100">{{q}}</textarea><br/>
  <button type="submit">Run</button>
</form>
{% if err %}<pre style="color:red">{{err}}</pre>{% endif %}
{% if rows %}
  <p>Rows: {{rows|length}}</p>
  <table border="1" cellpadding="4">
    <tr>{% for c in cols %}<th>{{c}}</th>{% endfor %}</tr>
    {% for r in rows %}<tr>{% for c in r %}<td>{{c}}</td>{% endfor %}</tr>{% endfor %}
  </table>
  <p><a href="/chart">📊 View Pie Chart</a></p>
{% endif %}
"""

app = Flask(__name__)

def allowed(sql:str)->bool:
    s=sql.strip().lower()
    return s.startswith("select") and " limit " in s and all(x not in s for x in
           [" insert ", " update ", " delete ", " drop ", " alter ", " create "])

def run_query(q):
    conn = pymysql.connect(host=DB_HOST,user=DB_USER,password=DB_PASS,
                           database=DB_NAME,autocommit=True,
                           cursorclass=pymysql.cursors.Cursor)
    try:
        with conn.cursor() as cur:
            cur.execute(q)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description] if cur.description else []
    finally:
        conn.close()
    return rows, cols

@app.route("/", methods=["GET","POST"])
def index():
    q = request.form.get("q","SELECT * FROM stats ORDER BY timestamp DESC LIMIT 10;")
    if request.method == "POST":
        if not allowed(q):
            return render_template_string(TPL, q=q, err="Only SELECT with LIMIT is allowed.", rows=None, cols=None)
        try:
            rows, cols = run_query(q)
            app.config['LAST_RESULT'] = (rows, cols)  # Save for chart
            return render_template_string(TPL, q=q, err=None, rows=rows, cols=cols)
        except Exception as e:
            return render_template_string(TPL, q=q, err=str(e), rows=None, cols=None)
    return render_template_string(TPL, q=q, err=None, rows=None, cols=None)

@app.route("/chart")
def chart():
    data = app.config.get('LAST_RESULT')
    if not data:
        return "No query run yet", 400
    rows, cols = data

    # Example: sum cpu_usage and memory_usage
    cpu = sum(float(r[2]) for r in rows if r[2] is not None)
    mem = sum(float(r[3]) for r in rows if r[3] is not None)

    fig, ax = plt.subplots()
    ax.pie([cpu, mem], labels=["CPU Usage", "Memory Usage"], autopct='%1.1f%%')
    ax.set_title("CPU vs Memory Usage")

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    return send_file(img, mimetype='image/png')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8082)