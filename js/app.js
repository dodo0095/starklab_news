/**
 * StarkLab News — frontend (reads data/*.json, renders cards + ECharts river)
 */

const STALE_HOURS = 36; // show stale warning if data older than this

const $ = (sel) => document.querySelector(sel);

function formatNumber(n, digits = 2) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString("zh-TW", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatPct(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${Number(n).toFixed(2)}%`;
}

function formatChange(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${formatNumber(n, 2)}`;
}

function directionClass(change) {
  if (change === null || change === undefined || Number.isNaN(change) || change === 0) {
    return "flat";
  }
  return change > 0 ? "up" : "down";
}

function parseTime(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

function formatDateTime(iso) {
  const d = parseTime(iso);
  if (!d) return "—";
  return d.toLocaleString("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function hoursSince(iso) {
  const d = parseTime(iso);
  if (!d) return Infinity;
  return (Date.now() - d.getTime()) / (1000 * 60 * 60);
}

function isStale(iso) {
  return hoursSince(iso) > STALE_HOURS;
}

async function loadJSON(path) {
  try {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return { ok: true, data: await res.json() };
  } catch (err) {
    console.warn(`Failed to load ${path}:`, err);
    return { ok: false, error: err.message || String(err) };
  }
}

function setGlobalMeta(updatedList) {
  const el = $("#global-updated");
  const badge = $("#freshness-badge");
  const valid = updatedList.filter(Boolean);
  if (!valid.length) {
    el.textContent = "尚無資料";
    badge.textContent = "無資料";
    badge.className = "badge warn";
    return;
  }
  // show most recent update among panels
  const latest = valid
    .map(parseTime)
    .filter(Boolean)
    .sort((a, b) => b - a)[0];
  if (!latest) {
    el.textContent = "—";
    return;
  }
  el.textContent = latest.toLocaleString("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const hrs = (Date.now() - latest.getTime()) / (1000 * 60 * 60);
  if (hrs > STALE_HOURS) {
    badge.textContent = "資料可能過期";
    badge.className = "badge warn";
  } else {
    badge.textContent = "資料就緒";
    badge.className = "badge ok";
  }
}

/* ---------- Market ---------- */
function renderMarket(result) {
  const root = $("#market-cards");
  const status = $("#market-status");

  if (!result.ok || !result.data) {
    root.innerHTML = "";
    status.className = "state-box error";
    status.hidden = false;
    status.textContent = "市場資料載入失敗，請稍後重新整理或執行資料更新腳本。";
    return null;
  }

  const data = result.data;
  const indices = data.indices || [];

  if (!indices.length) {
    root.innerHTML = "";
    status.className = "state-box";
    status.hidden = false;
    status.textContent = "資料更新中 — 尚無市場指數。";
    return data.updated_at;
  }

  if (isStale(data.updated_at)) {
    status.className = "state-box stale";
    status.hidden = false;
    status.textContent = `資料可能過期（更新於 ${formatDateTime(data.updated_at)}），仍顯示上次成功資料。`;
  } else {
    status.hidden = true;
  }

  root.innerHTML = indices
    .map((item) => {
      const dir = directionClass(item.change);
      return `
        <article class="card ${dir}">
          <p class="name">${escapeHtml(item.name || item.symbol || "—")}</p>
          <p class="value">${formatNumber(item.value, 2)}</p>
          <p class="change">${formatChange(item.change)}（${formatPct(item.change_pct)}）</p>
        </article>
      `;
    })
    .join("");

  return data.updated_at;
}

/* ---------- News ---------- */
function renderNews(result) {
  const root = $("#news-list");
  const status = $("#news-status");

  if (!result.ok || !result.data) {
    root.innerHTML = "";
    status.className = "state-box error";
    status.hidden = false;
    status.textContent = "新聞資料載入失敗。";
    return null;
  }

  const data = result.data;
  const items = (data.items || []).slice(0, 5);

  if (!items.length) {
    root.innerHTML = "";
    status.className = "state-box";
    status.hidden = false;
    status.textContent = "資料更新中 — 尚無重大新聞。";
    return data.updated_at;
  }

  if (isStale(data.updated_at)) {
    status.className = "state-box stale";
    status.hidden = false;
    status.textContent = `新聞資料可能過期（更新於 ${formatDateTime(data.updated_at)}）。`;
  } else {
    status.hidden = true;
  }

  root.innerHTML = items
    .map((item) => {
      const tags = (item.tags || [])
        .map((t) => `<span class="tag">${escapeHtml(t)}</span>`)
        .join("");
      const url = item.url || "#";
      return `
        <article class="news-item">
          <div class="title-row">
            <span class="rank">${item.rank ?? "·"}</span>
            <a class="title" href="${escapeAttr(url)}" target="_blank" rel="noopener noreferrer">
              ${escapeHtml(item.title || "（無標題）")}
            </a>
          </div>
          <p class="summary">${escapeHtml(item.summary || "")}</p>
          <div class="meta">
            <span>${escapeHtml(item.source || "—")}</span>
            <span>${formatDateTime(item.time)}</span>
            ${tags}
          </div>
        </article>
      `;
    })
    .join("");

  return data.updated_at;
}

/* ---------- Events ---------- */
function renderEvents(result) {
  const section = $("#events-section");
  const root = $("#events-list");
  const status = $("#events-status");

  if (!result.ok || !result.data) {
    section.hidden = false;
    root.innerHTML = "";
    status.className = "state-box";
    status.hidden = false;
    status.textContent = "事件資料暫不可用（可略過）。";
    return null;
  }

  const data = result.data;
  const events = (data.events || []).filter((e) => e.visible !== false);

  if (!events.length) {
    // P0 加分：沒有資料就整塊隱藏
    section.hidden = true;
    return data.updated_at;
  }

  section.hidden = false;
  status.hidden = true;

  root.innerHTML = events
    .map((ev) => {
      const actual =
        ev.actual === null || ev.actual === undefined
          ? "待公布"
          : formatNumber(ev.actual, 0);
      const forecast =
        ev.forecast === null || ev.forecast === undefined
          ? "—"
          : formatNumber(ev.forecast, 0);
      const previous =
        ev.previous === null || ev.previous === undefined
          ? "—"
          : formatNumber(ev.previous, 0);
      const unit = ev.unit ? ` ${escapeHtml(ev.unit)}` : "";
      return `
        <article class="event-card">
          <h3>${escapeHtml(ev.name || "事件")}</h3>
          <dl>
            <dt>日期</dt><dd>${escapeHtml(ev.date || "—")}</dd>
            <dt>預測</dt><dd>${forecast}${unit}</dd>
            <dt>前值</dt><dd>${previous}${unit}</dd>
            <dt>實際</dt><dd>${actual}${ev.actual != null ? unit : ""}</dd>
          </dl>
        </article>
      `;
    })
    .join("");

  return data.updated_at;
}

/* ---------- River chart ---------- */
function renderRiver(result) {
  const chartEl = $("#river-chart");
  const status = $("#chart-status");
  const titleEl = $("#chart-title");

  if (!result.ok || !result.data) {
    status.className = "state-box error";
    status.hidden = false;
    status.textContent = "河流圖資料載入失敗。";
    chartEl.style.display = "none";
    return null;
  }

  const data = result.data;
  const dates = data.dates || [];
  const series = data.series || {};
  const close = series.close || [];
  const ma5 = series.ma5 || [];
  const ma20 = series.ma20 || [];
  const ma60 = series.ma60 || [];

  if (!dates.length || !close.length) {
    status.className = "state-box";
    status.hidden = false;
    status.textContent = "資料更新中 — 尚無均線資料。";
    chartEl.style.display = "none";
    return data.updated_at;
  }

  if (isStale(data.updated_at)) {
    status.className = "state-box stale";
    status.hidden = false;
    status.textContent = `河流圖資料可能過期（更新於 ${formatDateTime(data.updated_at)}）。`;
  } else {
    status.hidden = true;
  }

  chartEl.style.display = "block";
  titleEl.textContent = `${data.name || data.symbol || "個股"} 河流圖`;

  const chart = echarts.init(chartEl);

  // Band between MA5 and MA20 for river feel
  const bandUpper = dates.map((_, i) => {
    const a = ma5[i];
    const b = ma20[i];
    if (a == null || b == null) return null;
    return Math.max(a, b);
  });
  const bandLower = dates.map((_, i) => {
    const a = ma5[i];
    const b = ma20[i];
    if (a == null || b == null) return null;
    return Math.min(a, b);
  });
  // stack: lower base + height
  const bandBase = bandLower;
  const bandHeight = dates.map((_, i) => {
    if (bandUpper[i] == null || bandLower[i] == null) return null;
    return bandUpper[i] - bandLower[i];
  });

  const option = {
    // calmer palette: close / MA5 / MA20 / MA60
    color: ["#1c2430", "#c2410c", "#2563a8", "#6b7280"],
    textStyle: { color: "#4a5568", fontFamily: "system-ui, sans-serif" },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(255,255,255,0.96)",
      borderColor: "#e5e7eb",
      textStyle: { color: "#1c2430" },
      axisPointer: { type: "cross", crossStyle: { color: "#9ca3af" } },
      valueFormatter: (v) => (v == null ? "—" : formatNumber(v, 2)),
    },
    legend: {
      data: ["收盤", "MA5", "MA20", "MA60"],
      top: 4,
      textStyle: { color: "#4a5568" },
    },
    grid: {
      left: 52,
      right: 24,
      top: 48,
      bottom: 48,
    },
    xAxis: {
      type: "category",
      data: dates,
      boundaryGap: false,
      axisLine: { lineStyle: { color: "#d1d5db" } },
      axisLabel: {
        color: "#6b7280",
        formatter: (v) => {
          if (!v) return "";
          const parts = String(v).split("-");
          return parts.length >= 3 ? `${parts[1]}-${parts[2]}` : v;
        },
      },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: { color: "#6b7280" },
      splitLine: { lineStyle: { type: "dashed", color: "#eef0f3" } },
    },
    dataZoom: [
      { type: "inside", start: 40, end: 100 },
      {
        type: "slider",
        start: 40,
        end: 100,
        height: 18,
        bottom: 8,
        borderColor: "#e5e7eb",
        fillerColor: "rgba(37, 99, 168, 0.12)",
        handleStyle: { color: "#2563a8" },
        textStyle: { color: "#6b7280" },
      },
    ],
    series: [
      {
        name: "MA 色帶",
        type: "line",
        data: bandBase,
        lineStyle: { opacity: 0 },
        stack: "band",
        symbol: "none",
        areaStyle: { opacity: 0 },
        tooltip: { show: false },
        silent: true,
        legendHoverLink: false,
        z: 1,
      },
      {
        name: "MA 色帶填充",
        type: "line",
        data: bandHeight,
        lineStyle: { opacity: 0 },
        stack: "band",
        symbol: "none",
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(194, 65, 12, 0.16)" },
            { offset: 1, color: "rgba(37, 99, 168, 0.12)" },
          ]),
        },
        tooltip: { show: false },
        silent: true,
        legendHoverLink: false,
        z: 1,
      },
      {
        name: "收盤",
        type: "line",
        data: close,
        showSymbol: false,
        lineStyle: { width: 2.1, color: "#1c2430" },
        z: 4,
      },
      {
        name: "MA5",
        type: "line",
        data: ma5,
        showSymbol: false,
        lineStyle: { width: 1.5, color: "#c2410c" },
        z: 3,
      },
      {
        name: "MA20",
        type: "line",
        data: ma20,
        showSymbol: false,
        lineStyle: { width: 1.5, color: "#2563a8" },
        z: 3,
      },
      {
        name: "MA60",
        type: "line",
        data: ma60,
        showSymbol: false,
        lineStyle: { width: 1.2, type: "dashed", color: "#6b7280" },
        z: 2,
      },
    ],
  };

  chart.setOption(option);
  window.addEventListener("resize", () => chart.resize());

  return data.updated_at;
}

/* ---------- utils ---------- */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttr(str) {
  return escapeHtml(str).replace(/'/g, "&#39;");
}

/* ---------- boot ---------- */
async function main() {
  $("#session-label").textContent = guessSession();

  const [market, news, stock, events] = await Promise.all([
    loadJSON("data/market.json"),
    loadJSON("data/news.json"),
    loadJSON("data/stock_ma.json"),
    loadJSON("data/events.json"),
  ]);

  const updated = [
    renderMarket(market),
    renderNews(news),
    renderRiver(stock),
    renderEvents(events),
  ];

  setGlobalMeta(updated);
}

function guessSession() {
  // rough label for TW timezone feel; display only
  try {
    const now = new Date();
    const tw = new Date(
      now.toLocaleString("en-US", { timeZone: "Asia/Taipei" })
    );
    const h = tw.getHours();
    if (h < 8) return "台股開盤前整理時段";
    if (h < 13) return "台股盤中";
    if (h < 21) return "美股開盤前整理時段";
    return "美股盤中 / 夜間";
  } catch {
    return "一般時段";
  }
}

main();
