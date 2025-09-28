#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Combined SQL console + interactive dashboard.

Exposes:
  GET  /              -> dashboard UI (query editor + KPIs + chart)
  POST /api/query     -> { sql: "SELECT ..." } -> rows + summary
  GET  /api/query     -> re-run last query (for auto-refresh)
Safeguards:
  - Only allows SELECT (no INSERT/UPDATE/DELETE/DDL)
  - Requires a LIMIT (caps to 1000)
"""

import os
import re
import json
from datetime import datetime
from typing import Tuple, List, Dict

from flask import Flask, request, jsonify, render_template, abort
import pymysql

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8082"))

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_USER = os.getenv("DB_USER", "devops")
DB_PASS = os.getenv("DB_PASS", "")
DB_NAME = os.getenv("DB_NAME", "syslogs")

DEFAULT_QUERY = os.getenv(
    "DEFAULT_QUERY",
    "SELECT memory_usage, cpu_usage, timestamp FROM stats ORDER BY timestamp DESC LIMIT 100;"
).strip()

# simple “last query” memory for auto-refresh
_last_sql = DEFAULT_QUERY

app = Flask(__name__, template_folder="templates", static_folder="static")


def get_db():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def _validate_sql(sql: str) -> Tuple[bool, str]:
    """Only allow read-only SELECT with a LIMIT (<= 1000)."""
    s = sql.strip().rstrip(";")
    # must start with SELECT
    if not re.match(r"(?is)^\s*select\b", s):
        return False, "Only SELECT statements are allowed."
    # forbid dangerous keywords
    if re.search(r"(?is)\b(insert|update|delete|drop|alter|create|truncate|grant|revoke)\b", s):
        return False, "Only read-only SELECT is allowed."
    # must have LIMIT
    m = re.search(r"(?is)\blimit\s+(\d+)\b", s)
    if not m:
        return False, "Please include a LIMIT (e.g. LIMIT 100)."
    # cap LIMIT to 1000
    try:
        lim = int(m.group(1))
        if lim > 1000:
            s = re.sub(r"(?is)\blimit\s+\d+\b", "LIMIT 1000", s)
    except Exception:
        return False, "Invalid LIMIT value."
    return True, s + ";"


def _summarize(rows: List[Dict]) -> Dict:
    """Compute quick KPIs from common column names if present."""
    if not rows:
        return {"avg_memory": None, "avg_cpu": None, "count": 0}
    def avg(col):
        vals = [r[col] for r in rows if col in r and isinstance(r[col], (int, float))]
        return round(sum(vals) / len(vals), 2) if vals else None
    return {
        "avg_memory": avg("memory_usage"),
        "avg_cpu": avg("cpu_usage"),
        "count": len(rows),
    }


def _run_sql(sql: str) -> Tuple[List[str], List[Dict], Dict]:
    ok, cleaned = _validate_sql(sql)
    if not ok:
        abort(400, cleaned)
    with get_db() as conn, conn.cursor() as cur:
        cur.execute(cleaned)
        rows = cur.fetchall()
        cols = list(rows[0].keys()) if rows else []
    return cols, rows, _summarize(rows)


@app.route("/", methods=["GET"])
def home():
    return render_template("dashboard.html", default_query=DEFAULT_QUERY)


@app.route("/api/query", methods=["GET", "POST"])
def api_query():
    global _last_sql
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        sql = (data.get("sql") or "").strip()
        if not sql:
            abort(400, "Missing 'sql' in JSON body.")
        _last_sql = sql  # remember last SQL for auto-refresh
    else:
        sql = _last_sql
    cols, rows, summary = _run_sql(sql)
    return jsonify({"columns": cols, "rows": rows, "summary": summary, "sql": sql})


@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    app.run(host=APP_HOST, port=APP_PORT, debug=False)
