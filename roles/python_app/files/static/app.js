(function () {
  const sqlBox = document.getElementById('sqlBox');
  const runBtn = document.getElementById('runBtn');
  const liveChk = document.getElementById('liveChk');
  const statusEl = document.getElementById('status');
  const kpiMem = document.getElementById('kpiMem');
  const kpiCpu = document.getElementById('kpiCpu');
  const table = document.getElementById('resultTable');
  const rowsCount = document.getElementById('rowsCount');

  let lastSQL = sqlBox.value.trim();
  let timer = null;

  // Chart.js line with 2 datasets
  const ctx = document.getElementById('chart').getContext('2d');
  const chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        { label: 'Memory Usage', data: [], tension: 0.25 },
        { label: 'CPU Usage',    data: [], tension: 0.25 },
      ],
    },
    options: {
      animation: false,
      scales: { x: { ticks: { maxRotation: 0, autoSkip: true } } },
      interaction: { mode: 'nearest', intersect: false },
      plugins: { legend: { position: 'bottom' } },
    }
  });

  function setStatus(msg) {
    statusEl.textContent = msg || '';
  }

  function toTimeLabel(v) {
    // try timestamp column if present
    try {
      const d = new Date(v);
      if (!isNaN(d.getTime())) return d.toLocaleTimeString();
    } catch {}
    return String(v);
  }

  function renderTable(columns, rows) {
    const thead = `<thead><tr>${columns.map(c => `<th>${c}</th>`).join('')}</tr></thead>`;
    const tbody = `<tbody>${
      rows.map(r => `<tr>${columns.map(c => `<td>${r[c] ?? ''}</td>`).join('')}</tr>`).join('')
    }</tbody>`;
    table.innerHTML = thead + tbody;
    rowsCount.textContent = `Rows: ${rows.length}`;
  }

  function updateKpis(summary) {
    kpiMem.textContent = summary.avg_memory ?? '—';
    kpiCpu.textContent = summary.avg_cpu ?? '—';
  }

  function updateChart(columns, rows) {
    // find likely column names
    const memCol = columns.find(c => c.toLowerCase().includes('memory'));
    const cpuCol = columns.find(c => c.toLowerCase().includes('cpu'));
    const tsCol  = columns.find(c => c.toLowerCase().includes('time')) || columns[0];

    const labels = rows.map(r => toTimeLabel(r[tsCol])).reverse();
    const mem = rows.map(r => Number(r[memCol] ?? null)).reverse();
    const cpu = rows.map(r => Number(r[cpuCol] ?? null)).reverse();

    chart.data.labels = labels;
    chart.data.datasets[0].data = mem;
    chart.data.datasets[1].data = cpu;
    chart.update();
  }

  async function runQuery(sql, userInitiated=false) {
    setStatus(userInitiated ? 'Running…' : 'Refreshing…');
    try {
      const res = await fetch('/api/query', {
        method: userInitiated ? 'POST' : 'GET',
        headers: { 'Content-Type': 'application/json' },
        body: userInitiated ? JSON.stringify({ sql }) : null
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || res.statusText);

      lastSQL = data.sql;
      if (userInitiated) sqlBox.value = lastSQL; // normalize spaces/casing

      renderTable(data.columns, data.rows);
      updateKpis(data.summary);
      updateChart(data.columns, data.rows);
      setStatus(`OK (${data.rows.length} rows)`);
    } catch (err) {
      setStatus(`Error: ${err.message}`);
    }
  }

  runBtn.addEventListener('click', () => {
    runQuery(sqlBox.value.trim(), true);
  });

  // live refresh the **last** SQL (the one you ran)
  function startTimer() {
    if (timer) clearInterval(timer);
    timer = setInterval(() => runQuery(lastSQL, false), 5000);
  }
  function stopTimer() {
    if (timer) clearInterval(timer);
    timer = null;
  }
  liveChk.addEventListener('change', () => liveChk.checked ? startTimer() : stopTimer());

  // initial load
  runQuery(lastSQL, true).then(() => {
    if (liveChk.checked) startTimer();
  });
})();
