import os
import json
import pymysql
from datetime import datetime
from flask import Flask, request, render_template_string, jsonify

app = Flask(__name__)

# ---- Config from environment (.env rendered by env_vars.j2) ----
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "")
DB_NAME = os.getenv("DB_NAME", "syslogs")

DEFAULT_QUERY = os.getenv(
    "DEFAULT_QUERY",
    "SELECT memory_usage, cpu_usage, timestamp FROM stats ORDER BY timestamp DESC LIMIT 100;"
).strip()

REFRESH_MS = int(os.getenv("REFRESH_MS", "5000"))  # auto refresh period
MAX_POINTS = int(os.getenv("MAX_POINTS", "120"))   # client-side clamp

# ---- Helpers ----
BLOCKLIST = {"insert", "update", "delete", "drop", "alter", "create", "truncate", "grant", "revoke"}

def is_safe_select(sql: str) -> bool:
    s = " ".join(sql.strip().split()).lower()
    if not s.startswith("select "):
        return False
    # naive guard rails; good enough for a read-only console on a private demo box
    return not any(b in s for b in BLOCKLIST)

def run_query(sql: str):
    conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, db=DB_NAME, cursorclass=pymysql.cursors.Cursor)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            columns = [d[0] for d in cur.description]
            return {"columns": columns, "rows": [list(r) for r in rows]}
    finally:
        conn.close()

# ---- Routes ----
@app.route("/", methods=["GET"])
def index():
    # Initial page with textarea + table + live charts
    return render_template_string("""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Read-only SQL Console + Live Dashboard</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 16px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    textarea { width: 100%; height: 120px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; }
    table { border-collapse: collapse; width: 100%; margin-top: 8px; }
    th, td { border: 1px solid #ddd; padding: 6px 8px; font-size: 14px; }
    th { background: #f6f6f6; text-align: left; }
    .card { border: 1px solid #eee; border-radius: 12px; padding: 16px; box-shadow: 0 1px 8px rgba(0,0,0,0.05); }
    .row { display: flex; gap: 12px; align-items: center; }
    button { padding: 8px 12px; border-radius: 8px; border: 1px solid #ddd; cursor: pointer; background: #fff; }
    .muted { color: #777; font-size: 12px; }
  </style>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
  <h2>Read-only SQL Console</h2>
  <div class="grid">
    <div class="card">
      <form id="qform" class="row" onsubmit="return false;">
        <textarea id="query">{{ default_query }}</textarea>
      </form>
      <div class="row" style="margin-top:8px">
        <button onclick="runOnce()">Run</button>
        <span class="muted">Auto-refresh every {{ refresh_ms/1000 }}s</span>
        <span id="status" class="muted"></span>
      </div>

      <div id="table-wrap"></div>
    </div>

    <div class="card">
      <h3 style="margin-top:0">Performance Dashboard</h3>
      <canvas id="memChart" height="120"></canvas>
      <div style="height:20px"></div>
      <canvas id="cpuChart" height="120"></canvas>
    </div>
  </div>

<script>
const REFRESH_MS = {{ refresh_ms }};
const MAX_POINTS = {{ max_points }};
let memChart, cpuChart;

function fmtTs(ts) {
  try {
    return new Date(ts.replace(' ','T') + 'Z').toLocaleTimeString();
  } catch(e) {
    return ts;
  }
}

function renderTable(data) {
  if (!data || !data.columns) return;
  const ths = data.columns.map(c => `<th>${c}</th>`).join('');
  const rows = (data.rows || []).map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('');
  document.getElementById('table-wrap').innerHTML =
    `<table><thead><tr>${ths}</tr></thead><tbody>${rows}</tbody></table>`;
}

function buildCharts() {
  const ctx1 = document.getElementById('memChart').getContext('2d');
  const ctx2 = document.getElementById('cpuChart').getContext('2d');
  memChart = new Chart(ctx1, {
    type: 'line',
    data: { labels: [], datasets: [{ label: 'Memory Usage', data: [] }] },
    options: { animation:false, responsive:true, scales:{x:{title:{display:true,text:'time'}}, y:{title:{display:true,text:'%'}}}}
  });
  cpuChart = new Chart(ctx2, {
    type: 'line',
    data: { labels: [], datasets: [{ label: 'CPU Usage', data: [] }] },
    options: { animation:false, responsive:true, scales:{x:{title:{display:true,text:'time'}}, y:{title:{display:true,text:'%'}}}}
  });
}

function updateCharts(data) {
  // Only update if columns include timestamp, memory_usage, cpu_usage
  const cols = (data.columns || []).map(c => c.toLowerCase());
  const iTs = cols.indexOf('timestamp');
  const iMem = cols.indexOf('memory_usage');
  const iCpu = cols.indexOf('cpu_usage');
  const canChart = (iTs >= 0 && iMem >= 0 && iCpu >= 0);

  if (!canChart) {
    document.getElementById('status').innerText = '(table updated; charts hidden – query must return timestamp, memory_usage, cpu_usage)';
    memChart.data.labels = []; memChart.data.datasets[0].data = [];
    cpuChart.data.labels = []; cpuChart.data.datasets[0].data = [];
    memChart.update(); cpuChart.update();
    return;
  }

  const rows = data.rows.slice(0, MAX_POINTS).reverse(); // oldest->newest
  const labels = rows.map(r => fmtTs(String(r[iTs])));
  const mem = rows.map(r => Number(r[iMem]));
  const cpu = rows.map(r => Number(r[iCpu]));

  memChart.data.labels = labels;
  memChart.data.datasets[0].data = mem;
  cpuChart.data.labels = labels;
  cpuChart.data.datasets[0].data = cpu;

  memChart.update();
  cpuChart.update();
  document.getElementById('status').innerText = '(live)';
}

async function fetchData(query) {
  const res = await fetch('/api/query', {
    method:'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ query })
  });
  if (!res.ok) throw new Error('Query failed');
  return await res.json();
}

async function refreshLoop() {
  try {
    const q = document.getElementById('query').value;
    const data = await fetchData(q);
    renderTable(data);
    updateCharts(data);
  } catch (e) {
    document.getElementById('status').innerText = '(error)';
    console.error(e);
  } finally {
    setTimeout(refreshLoop, REFRESH_MS);
  }
}

async function runOnce() {
  try {
    const q = document.getElementById('query').value;
    const data = await fetchData(q);
    renderTable(data);
    updateCharts(data);
  } catch (e) {
    alert('Query error. Only SELECT is allowed.');
  }
}

buildCharts();
runOnce();
setTimeout(refreshLoop, REFRESH_MS);
</script>
</body>
</html>
    """, default_query=DEFAULT_QUERY, refresh_ms=REFRESH_MS, max_points=MAX_POINTS)

@app.route("/api/query", methods=["POST"])
def api_query():
    payload = request.get_json(silent=True) or {}
    q = (payload.get("query") or DEFAULT_QUERY).strip()
    if not is_safe_select(q):
        return jsonify({"error": "Only SELECT queries are allowed."}), 400

    # Safety clamp if user didn't limit
    if " limit " not in q.lower():
        q = f"{q.rstrip(';')} LIMIT {MAX_POINTS};"

    try:
        data = run_query(q)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Runs behind systemd; keep host/port explicit
    app.run(host="0.0.0.0", port=8082)
