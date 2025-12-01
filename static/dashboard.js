// static/dashboard.js
let costChart = null;
let userChart = null;
// ctx.canvas.parentNode.style.height = "220px";

// --- Helpers ---
function isoDate(d) {
  try { return new Date(d).toISOString().split("T")[0]; }
  catch { return d; }
}

// Limit data to avoid huge charts
function limitChartData(data, maxPoints = 50) {
    if (data.length <= maxPoints) return data;
    return data.slice(data.length - maxPoints);
}

// --- METRICS CARDS ---
function renderMetrics(data) {
  const totalTokens = data.reduce((s, r) => s + (r.tokens_used || 0), 0);
  const totalCost = data.reduce((s, r) => s + (r.cost_usd || 0), 0);

  const apiEvents = data.filter(d => d.type && d.type.includes("api")).length;
  const llmEvents = data.filter(d => d.type && (d.type.includes("llm") || d.type.includes("generation"))).length;

  document.getElementById("metrics").innerHTML = `
    <div class="metric-card"><div class="metric-label">Total Tokens</div><div class="metric-value">${totalTokens}</div></div>
    <div class="metric-card"><div class="metric-label">Total Cost (USD)</div><div class="metric-value">$${totalCost.toFixed(6)}</div></div>
    <div class="metric-card"><div class="metric-label">API Events</div><div class="metric-value">${apiEvents}</div></div>
    <div class="metric-card"><div class="metric-label">LLM Events</div><div class="metric-value">${llmEvents}</div></div>
  `;
}

// --- COST CHART ---
function renderCostChart(data) {
  data = limitChartData(data, 50);

  const costByDate = {};
  data.forEach(d => {
    const dt = isoDate(d.timestamp || "");
    costByDate[dt] = (costByDate[dt] || 0) + (d.cost_usd || 0);
  });

  const labels = Object.keys(costByDate).sort();
  const values = labels.map(l => costByDate[l]);

  const ctx = document.getElementById("costChart").getContext("2d");

  // FIX HEIGHT HERE
  ctx.canvas.parentNode.style.height = "220px";

  if (costChart) costChart.destroy();

  costChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Cost USD",
        data: values,
        borderColor: "#FF8A00",
        backgroundColor: "rgba(255,138,0,0.08)",
        fill: true
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false  // REQUIRED for custom height to work
    }
  });
}


// --- USER CHART ---
function renderUserChart(data) {
  data = limitChartData(data, 50); // SHORTEN CHART

  const counts = {};
  data.forEach(d => {
    const u = d.user_id || "unknown";
    counts[u] = (counts[u] || 0) + 1;
  });

  const labels = Object.keys(counts);
  const values = labels.map(l => counts[l]);

  const ctx = document.getElementById("userChart").getContext("2d");
  ctx.canvas.parentNode.style.height = "220px";
  if (userChart) userChart.destroy();

  userChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Events",
        data: values,
        backgroundColor: "#2dd4bf"
      }]
    },
    options: { responsive: true, maintainAspectRatio: false }
  });
}

// --- TABLE ---
function renderTable(data) {
  const wrap = document.getElementById("table-wrap");
  if (!data || data.length === 0) {
    wrap.innerHTML = "<div class='muted'>No events to show</div>";
    return;
  }

  const cols = ["timestamp","user_id","type","model","tokens_used","cost_usd","url"];
  let html = "<table class='table'><thead><tr>";

  cols.forEach(c => html += `<th>${c}</th>`);
  html += "</tr></thead><tbody>";

  data.forEach(r => {
    html += "<tr>";
    cols.forEach(c => {
      let v = r[c];
      if (c === "timestamp")
        v = r.timestamp ? new Date(r.timestamp).toLocaleString() : "";
      html += `<td>${v ?? ""}</td>`;
    });
    html += "</tr>";
  });

  html += "</tbody></table>";
  wrap.innerHTML = html;
}

// --- LOAD DATA (Manual Refresh) ---
async function loadData() {
  const user = encodeURIComponent(document.getElementById("user-filter").value || "");
  const limit = encodeURIComponent(document.getElementById("max-rows").value || 1000);
  const last_n_days = encodeURIComponent(document.getElementById("last-n-days").value || 30);

  const res = await fetch(`/api/events?user=${user}&limit=${limit}&last_n_days=${last_n_days}`);
  latestData = await res.json();

  document.getElementById("last-updated").innerText =
    `Last updated: ${new Date().toLocaleString()}`;

  renderMetrics(latestData);
  renderCostChart(latestData);
  renderUserChart(latestData);
  renderTable(latestData);
}

// Buttons
document.getElementById("apply-btn").addEventListener("click", loadData);
document.getElementById("refresh-btn").addEventListener("click", loadData);

// --- REALTIME SSE STREAM ---
let latestData = [];
let needsUpdate = false;

function startRealtimeStream() {
  const evtSource = new EventSource("/events/stream");

  evtSource.onmessage = function (event) {
    try {
      const newEvents = JSON.parse(event.data);
      if (!Array.isArray(newEvents)) return;

      latestData = newEvents.concat(latestData);

      if (latestData.length > 300)
        latestData = latestData.slice(0, 300);

      // Mark that there are new events, but DO NOT re-render yet
      needsUpdate = true;

    } catch (e) {
      console.error("Realtime parse error:", e);
    }
  };

  evtSource.onerror = function () {
    console.warn("SSE disconnected. Reconnecting in 2s...");
    setTimeout(startRealtimeStream, 2000);
  };
}

// Render dashboard only once every 5 seconds
setInterval(() => {
  if (!needsUpdate) return;
  needsUpdate = false;

  renderMetrics(latestData);
  renderCostChart(latestData);
  renderUserChart(latestData);
  renderTable(latestData);

  document.getElementById("last-updated").innerText =
    `Last updated: ${new Date().toLocaleString()}`;

}, 5000); // ← UPDATE EVERY 5 SECONDS

// Initial load
loadData().then(() => startRealtimeStream());
