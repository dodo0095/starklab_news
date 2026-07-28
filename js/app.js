/**
 * StarkLab News — frontend (讀 data/*.json，繪製格子化儀表板)
 * 主角：本益比（PE）河流圖。其餘：市場總覽 / 重大新聞 / TSMC / 聯準會 / 摘要 / 事件。
 */

const STALE_HOURS = 36;
const $ = (sel) => document.querySelector(sel);

/* ---------- format utils ---------- */
function formatNumber(n, digits = 2) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString("zh-TW", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}
function formatPct(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return `${n > 0 ? "+" : ""}${Number(n).toFixed(2)}%`;
}
function formatChange(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return `${n > 0 ? "+" : ""}${formatNumber(n, 2)}`;
}
function directionClass(change) {
  if (change === null || change === undefined || Number.isNaN(change) || change === 0) return "flat";
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
  return d.toLocaleString("zh-TW", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
}
function hoursSince(iso) {
  const d = parseTime(iso);
  return d ? (Date.now() - d.getTime()) / 3.6e6 : Infinity;
}
function isStale(iso) { return hoursSince(iso) > STALE_HOURS; }
function escapeHtml(str) {
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function escapeAttr(str) { return escapeHtml(str).replace(/'/g, "&#39;"); }

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

function setStatus(el, kind, msg) {
  if (!el) return;
  el.className = `state-box${kind ? " " + kind : ""}`;
  el.hidden = false;
  el.textContent = msg;
}

function setGlobalMeta(updatedList, statusRes) {
  const el = $("#global-updated");
  const badge = $("#freshness-badge");
  // 優先用排程心跳（status.json 的 ran_at）：即使某來源資料沒變，也能證明排程有跑
  const st = statusRes && statusRes.ok ? statusRes.data : null;
  let latest = st && st.ran_at ? parseTime(st.ran_at) : null;
  if (!latest) {
    const valid = updatedList.filter(Boolean).map(parseTime).filter(Boolean).sort((a, b) => b - a);
    latest = valid[0] || null;
  }
  if (!latest) {
    el.textContent = "尚無資料";
    badge.textContent = "無資料";
    badge.className = "badge warn";
    return;
  }
  el.textContent = latest.toLocaleString("zh-TW", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
  // 排程每天 4 次（間隔最長約 8 小時）；逾 9 小時未更新 → 可能沒跑
  const stale = (Date.now() - latest.getTime()) / 3.6e6 > 9;
  badge.textContent = stale ? "可能未更新" : "資料就緒";
  badge.className = `badge ${stale ? "warn" : "ok"}`;
}

const SOURCE_NAME = {
  "fetch_market.py": "市場", "fetch_news.py": "新聞", "fetch_tsmc_news.py": "TSMC",
  "fetch_valuation.py": "本益比", "fetch_events.py": "事件", "fetch_fed.py": "Fed",
  "fetch_stock_ma.py": "均線", "fetch_heat.py": "熱度",
};
function renderSourceStatus(statusRes) {
  const el = $("#source-status");
  if (!el) return;
  if (!statusRes || !statusRes.ok || !statusRes.data || !Array.isArray(statusRes.data.sources)) {
    el.textContent = "尚無排程執行紀錄（首次請手動執行 run_all.py，或等待排程觸發）。";
    return;
  }
  const d = statusRes.data;
  const items = d.sources.map((s) => {
    const nm = SOURCE_NAME[s.script] || s.script;
    return `<span>${escapeHtml(nm)} <b class="${s.ok ? "ok" : "bad"}">${s.ok ? "✓" : "✗"}</b></span>`;
  }).join("");
  el.innerHTML = `<span>本次排程更新 ${escapeHtml(formatDateTime(d.ran_at))}（成功 ${d.ok_count}/${d.total}）</span>` + items;
}

/* ---------- Market ---------- */
function indexCardHtml(item) {
  const dir = directionClass(item.change);
  return `<article class="card ${dir}">
      <p class="name">${escapeHtml(item.name || item.symbol || "—")}</p>
      <p class="value">${formatNumber(item.value, 2)}</p>
      <p class="change">${formatChange(item.change)}（${formatPct(item.change_pct)}）</p>
    </article>`;
}

function renderIndexRow(indices, rootSel, statusSel, updatedAt, emptyMsg) {
  const root = $(rootSel);
  const status = $(statusSel);
  if (!root) return;
  if (!indices || !indices.length) {
    root.innerHTML = "";
    setStatus(status, "", emptyMsg);
    return;
  }
  if (isStale(updatedAt)) setStatus(status, "stale", `資料可能過期（更新於 ${formatDateTime(updatedAt)}），仍顯示上次成功資料。`);
  else status.hidden = true;
  root.innerHTML = indices.map(indexCardHtml).join("");
}

let marketState = null;
let currentMkt = "us"; // us | tw

function renderMarketGroup(which) {
  currentMkt = which;
  const d = marketState;
  if (!d) return;
  const isTw = which === "tw";
  const titleEl = $("#market-title");
  if (titleEl) titleEl.textContent = isTw ? "台股" : "美股 / 國際";
  const arr = (isTw ? d.tw_indices : d.indices) || [];
  const empty = isTw
    ? "資料更新中 — 請執行 fetch_market.py 取得台股資料。"
    : "資料更新中 — 尚無美股指數。";
  renderIndexRow(arr, "#market-cards", "#market-status", d.updated_at, empty);
}

function renderMarket(result) {
  if (!result.ok || !result.data) {
    $("#market-cards").innerHTML = "";
    setStatus($("#market-status"), "error", "市場資料載入失敗，請執行資料更新腳本或稍後重試。");
    marketState = null;
    return null;
  }
  marketState = result.data;
  renderMarketGroup(currentMkt);
  return result.data.updated_at;
}

/* ---------- 新聞清單（共用） ---------- */
function newsItemHtml(item, opts = {}) {
  const url = item.url || "#";
  const rank = opts.rank ? `<span class="rank">${item.rank ?? "·"}</span>` : "";
  const summary = item.summary ? `<p class="summary">${escapeHtml(item.summary)}</p>` : "";
  const stance = item.stance
    ? `<span class="stance ${item.stance}">${item.stance === "hawk" ? "偏鷹" : item.stance === "dove" ? "偏鴿" : "中性"}</span>`
    : "";
  const tags = (item.tags || []).map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("");
  return `<div class="news-item">${rank}<div class="news-body">
      <a class="title" href="${escapeAttr(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title || "（無標題）")}</a>
      ${summary}
      <div class="meta"><span class="src">${escapeHtml(item.source || "—")}</span><span>${formatDateTime(item.time)}</span>${stance}${tags}</div>
    </div></div>`;
}

function renderNewsList(result, rootSel, statusSel, opts = {}) {
  const root = $(rootSel);
  const status = $(statusSel);
  if (!result.ok || !result.data) {
    root.innerHTML = "";
    setStatus(status, "error", `${opts.label || "新聞"}資料載入失敗。`);
    return null;
  }
  const data = result.data;
  const items = (data.items || []).slice(0, opts.limit || 6);
  if (!items.length) {
    root.innerHTML = "";
    setStatus(status, "", `資料更新中 — 尚無${opts.label || "新聞"}。`);
    return data.updated_at;
  }
  if (isStale(data.updated_at)) setStatus(status, "stale", `${opts.label || "新聞"}資料可能過期（更新於 ${formatDateTime(data.updated_at)}）。`);
  else status.hidden = true;
  root.innerHTML = items.map((it) => newsItemHtml(it, opts)).join("");
  return data.updated_at;
}

/* ---------- 條列（摘要 / 支撐） ---------- */
function renderBullets(result, rootSel, key) {
  const root = $(rootSel);
  if (!root) return null;
  if (!result.ok || !result.data) { root.innerHTML = `<li>資料暫不可用。</li>`; return null; }
  const arr = result.data[key] || [];
  root.innerHTML = arr.length ? arr.map((t) => `<li>${escapeHtml(t)}</li>`).join("") : `<li>目前無內容。</li>`;
  return result.data.updated_at;
}

/* ---------- 消息面熱度（情緒溫度計） ---------- */
function renderHeat(result) {
  const status = $("#heat-status");
  const gEl = $("#heat-gauge");
  const dEl = $("#heat-drivers");
  if (!gEl) return null;
  if (!result.ok || !result.data) { setStatus(status, "note", "熱度資料暫不可用。"); gEl.style.display = "none"; return null; }
  const d = result.data;
  const score = typeof d.score === "number" ? d.score : 50;
  const level = d.level || "—";
  gEl.style.display = "block";
  const chart = echarts.getInstanceByDom(gEl) || echarts.init(gEl);
  chart.setOption({
    series: [{
      type: "gauge", min: 0, max: 100, startAngle: 200, endAngle: -20, radius: "96%", center: ["50%", "60%"],
      axisLine: { lineStyle: { width: 13, color: [[0.2, "#4a90d9"], [0.4, "#7bb0d8"], [0.6, "#cbb46a"], [0.8, "#e0975a"], [1, "#d24b46"]] } },
      pointer: { width: 5, length: "60%", itemStyle: { color: "#1b2330" } },
      anchor: { show: true, size: 10, itemStyle: { color: "#1b2330" } },
      axisTick: { show: false }, splitLine: { length: 11, lineStyle: { color: "#fff", width: 2 } }, axisLabel: { show: false },
      title: { show: false },
      detail: { valueAnimation: true, offsetCenter: [0, "34%"], formatter: () => `${level}  ${score}`, fontSize: 15, fontWeight: 700, color: "#1b2330" },
      data: [{ value: score }],
    }],
  }, true);
  window.addEventListener("resize", () => chart.resize());
  const demo = d.demo ? '<span class="demo-tag">示範</span>' : "";
  dEl.innerHTML = (d.drivers || []).map((x) => `<span class="chip">${escapeHtml(x)}</span>`).join("") + demo;
  status.hidden = true;
  return d.updated_at;
}

/* ---------- Events ---------- */
function renderEvents(result) {
  const root = $("#events-list");
  const status = $("#events-status");
  if (!result.ok || !result.data) { setStatus(status, "note", "事件資料暫不可用（可略過）。"); root.innerHTML = ""; return null; }
  const events = (result.data.events || []).filter((e) => e.visible !== false);
  if (!events.length) { setStatus(status, "note", "近期無重大月頻事件。"); root.innerHTML = ""; return result.data.updated_at; }
  status.hidden = true;
  root.innerHTML = events.map((ev) => {
    const fmt = (v) => (v === null || v === undefined ? "—" : formatNumber(v, 0));
    const unit = ev.unit ? ` ${escapeHtml(ev.unit)}` : "";
    const actual = ev.actual === null || ev.actual === undefined ? `<span class="await">待公布</span>` : `${fmt(ev.actual)}${unit}`;
    return `<article class="event-card">
      <h3>${escapeHtml(ev.name || "事件")}${ev.actual == null ? ' <span class="await">實際待公布</span>' : ""}</h3>
      <dl>
        <dt>公布日</dt><dd>${escapeHtml(ev.date || "—")}</dd>
        <dt>預測</dt><dd>${fmt(ev.forecast)}${unit}</dd>
        <dt>前值</dt><dd>${fmt(ev.previous)}${unit}</dd>
        <dt>實際</dt><dd>${actual}</dd>
      </dl>
    </article>`;
  }).join("");
  return result.data.updated_at;
}

/* ---------- 本益比河流圖 ---------- */
let valState = null;

// 參考正規本益比河流圖：冷（便宜/藍）→ 暖（昂貴/粉）漸層，五層色帶
const PE_FILL = [
  "rgba(106, 164, 216, 0.42)", // 最便宜（藍）
  "rgba(146, 192, 230, 0.40)", // 淺藍
  "rgba(190, 222, 240, 0.42)", // 更淺藍
  "rgba(248, 224, 146, 0.46)", // 米黃
  "rgba(242, 168, 150, 0.48)", // 粉橘（最貴）
];
const LINE_DOT = ["#6aa4d8", "#92c0e6", "#bee0f0", "#f6d98a", "#f3ac93", "#ec8a90"]; // 6 條倍數線 低→高
const PRICE_COLOR = "#b5372f"; // 沉穩暗紅（月均價）

function renderValuation(result) {
  const status = $("#chart-status");
  const titleEl = $("#val-title");
  const peEl = $("#val-pe");
  const zoneEl = $("#val-zone");
  const keyEl = $("#band-key");
  const chartEl = $("#river-chart");

  if (!result.ok || !result.data) {
    setStatus(status, "error", "本益比河流圖資料載入失敗（請執行 fetch_valuation.py）。");
    chartEl.style.display = "none";
    return null;
  }
  const data = result.data;
  valState = data;
  const dates = data.dates || [];
  const close = data.close || [];
  const lines = data.pe_lines || [];
  const bandPrices = data.band_prices || [];
  if (!dates.length || !close.length || bandPrices.length < 2) {
    setStatus(status, "", "資料更新中 — 尚無本益比資料。");
    chartEl.style.display = "none";
    return data.updated_at;
  }

  // 標題與落點
  titleEl.textContent = `${data.name || data.symbol || "個股"} 本益比河流圖`;
  peEl.textContent = data.current_pe != null ? `PE ${formatNumber(data.current_pe, 1)}` : "—";
  zoneEl.textContent = data.zone_label || "—";
  const nBand = bandPrices.length - 1;
  const bi = data.current_band_index;
  const zoneCls = bi == null ? "" : bi >= nBand - 1 ? "expensive" : bi <= 0 ? "cheap" : "fair";
  zoneEl.className = `zone-badge ${zoneCls}`;

  let staleMsg = "";
  if (data.approximate) staleMsg = "（近似估值帶：此標的季度 EPS 不可得，改用常數 EPS 計算）";
  if (isStale(data.updated_at)) setStatus(status, "stale", `資料可能過期（更新於 ${formatDateTime(data.updated_at)}）。${staleMsg}`);
  else if (staleMsg) setStatus(status, "note", staleMsg);
  else status.hidden = true;
  // 防呆：示範資料一律標紅，絕不讓假股價冒充真實股價
  if (data.demo) setStatus(status, "error", "⚠ 這是示範資料，不是真實股價。請執行 python scripts\\fetch_valuation.py 後按 Ctrl+F5 更新。");

  chartEl.style.display = "block";

  // 河流色帶：底線 = 最低倍數線，逐層堆疊高度形成五層色帶（色帶完整包住股價）
  const base = bandPrices[0];
  const heights = [];
  for (let b = 1; b < bandPrices.length; b++) {
    const hi = bandPrices[b], lo = bandPrices[b - 1];
    heights.push(dates.map((_, i) => (hi[i] == null || lo[i] == null ? null : Math.round((hi[i] - lo[i]) * 100) / 100)));
  }
  const lastClose = close[close.length - 1];
  const lastIdx = dates.length - 1;

  const series = [];
  // 基底（透明，不進 tooltip）
  series.push({ name: "_base", type: "line", data: base, stack: "riv", symbol: "none", lineStyle: { opacity: 0 }, areaStyle: { opacity: 0 }, silent: true, tooltip: { show: false } });
  // 各層色帶（藍→粉，無邊線）
  heights.forEach((h, i) => {
    series.push({ name: `_band${i}`, type: "line", data: h, stack: "riv", symbol: "none", lineStyle: { opacity: 0 }, areaStyle: { color: PE_FILL[i] || PE_FILL[PE_FILL.length - 1] }, silent: true, tooltip: { show: false } });
  });
  // 月均價（主角線，沉穩暗紅）+ 現價標記
  series.push({
    name: "月均價", type: "line", data: close, symbol: "none", smooth: false,
    lineStyle: { width: 2.4, color: PRICE_COLOR }, z: 6,
    markPoint: {
      symbol: "circle", symbolSize: 9, z: 8,
      itemStyle: { color: PRICE_COLOR, borderColor: "#fff", borderWidth: 2 },
      label: { show: true, position: "left", distance: 10, color: PRICE_COLOR, fontWeight: 700, fontSize: 12,
        backgroundColor: "rgba(255,255,255,0.9)", padding: [3, 5], borderRadius: 4,
        formatter: () => `現價 ${formatNumber(lastClose, 0)}` },
      data: [{ coord: [lastIdx, lastClose] }], silent: true,
    },
  });

  const chart = echarts.getInstanceByDom(chartEl) || echarts.init(chartEl);
  chart.setOption({
    animationDuration: 500,
    textStyle: { color: "#4a5568", fontFamily: "system-ui, 'Noto Sans TC', sans-serif" },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(255,255,255,0.97)", borderColor: "#e5e7eb", borderWidth: 1,
      textStyle: { color: "#1c2430", fontSize: 12 },
      axisPointer: { type: "line", lineStyle: { color: "#c7ccd4" } },
      formatter: (ps) => {
        if (!ps || !ps.length) return "";
        const price = ps.find((p) => p.seriesName === "月均價");
        const i = price ? price.dataIndex : ps[0].dataIndex;
        const c = close[i];
        let k = 0;
        for (let b = 0; b < bandPrices.length; b++) { if (c != null && bandPrices[b][i] != null && c >= bandPrices[b][i]) k = b; }
        const peLo = lines[k], peHi = lines[Math.min(k + 1, lines.length - 1)];
        return `<b>${ps[0].axisValue}</b><br/>月均價 <b>${formatNumber(c, 0)}</b>` +
          `<br/><span style="color:#8a8f98">約 ${formatNumber(peLo, 1)}–${formatNumber(peHi, 1)} 倍本益比</span>`;
      },
    },
    grid: { left: 8, right: 18, top: 16, bottom: 40, containLabel: true },
    xAxis: {
      type: "category", data: dates, boundaryGap: false,
      axisLine: { lineStyle: { color: "#e0e3e8" } }, axisTick: { show: false },
      axisLabel: { color: "#9199a4", hideOverlap: true, formatter: (v) => { const p = String(v).split("-"); return p.length >= 3 ? `${p[0]}/${p[1]}` : v; } },
    },
    yAxis: {
      type: "value", scale: true, position: "right",
      axisLabel: { color: "#9199a4", formatter: (v) => formatNumber(v, 0) },
      splitLine: { lineStyle: { color: "#f0f1f4" } }, axisLine: { show: false }, axisTick: { show: false },
    },
    dataZoom: [
      { type: "inside", start: 0, end: 100 },
      { type: "slider", start: 0, end: 100, height: 15, bottom: 6, borderColor: "transparent",
        backgroundColor: "#f4f5f7", fillerColor: "rgba(37,99,168,0.10)",
        handleStyle: { color: "#2563a8" }, moveHandleStyle: { color: "#c7ccd4" }, textStyle: { color: "#9199a4", fontSize: 10 } },
    ],
    series,
  }, true);
  window.addEventListener("resize", () => chart.resize());

  // 帶說明：6 條倍數線（藍→粉）+ 月均價，對齊參考圖
  keyEl.innerHTML = lines.map((pe, i) =>
    `<span><i style="background:${LINE_DOT[i] || LINE_DOT[LINE_DOT.length - 1]}"></i>${formatNumber(pe, 1)} 倍本益比</span>`
  ).join("") + `<span><i style="background:${PRICE_COLOR}"></i>月均價</span>`;
  return data.updated_at;
}

/* ---------- 控制項：代碼查詢 / PE-PB 切換 ---------- */
function wireControls() {
  const go = $("#val-go");
  const input = $("#val-ticker");
  const status = $("#chart-status");
  function query() {
    const raw = (input.value || "").trim().replace(/\s.*$/, "");
    const loaded = valState ? String(valState.symbol || "").replace(/\..*$/, "") : "";
    if (!raw || raw === loaded) return;
    setStatus(status, "note",
      `目前示範標的為 ${valState ? valState.name : "台積電"}（${loaded}）。切換其他標的：在後端執行 ` +
      `STOCK_SYMBOL=${raw}.TW python scripts/fetch_valuation.py 後重新整理即可。`);
  }
  if (go) go.addEventListener("click", query);
  if (input) input.addEventListener("keydown", (e) => { if (e.key === "Enter") query(); });

  // 市場總覽 美股/台股 切換
  const mseg = $("#market-seg");
  if (mseg) {
    mseg.querySelectorAll("span").forEach((sp) => {
      sp.addEventListener("click", () => {
        mseg.querySelectorAll("span").forEach((x) => x.classList.remove("on"));
        sp.classList.add("on");
        renderMarketGroup(sp.dataset.mkt);
      });
    });
  }

  const seg = $("#val-metric");
  if (seg) {
    seg.querySelectorAll("span").forEach((sp) => {
      sp.addEventListener("click", () => {
        seg.querySelectorAll("span").forEach((x) => x.classList.remove("on"));
        sp.classList.add("on");
        if (sp.dataset.metric === "PB") {
          setStatus(status, "note", "淨值比（PB）河流圖為 P1 項目，稍後開放；目前顯示本益比（PE）。");
        } else if (valState) {
          status.hidden = true;
          renderValuation({ ok: true, data: valState });
        }
      });
    });
  }
}

/* ---------- boot ---------- */
async function main() {
  $("#session-label").textContent = guessSession();
  wireControls();

  const [market, news, tsmc, valuation, events, fed, summary, heat, status] = await Promise.all([
    loadJSON("data/market.json"),
    loadJSON("data/news.json"),
    loadJSON("data/tsmc_news.json"),
    loadJSON("data/valuation.json"),
    loadJSON("data/events.json"),
    loadJSON("data/fed.json"),
    loadJSON("data/summary.json"),
    loadJSON("data/heat.json"),
    loadJSON("data/status.json"),
  ]);

  const updated = [
    renderMarket(market),
    renderHeat(heat),
    renderNewsList(news, "#news-list", "#news-status", { rank: true, limit: 5, label: "重大新聞" }),
    renderNewsList(tsmc, "#tsmc-list", "#tsmc-status", { limit: 6, label: "台積電新聞" }),
    renderValuation(valuation),
    renderEvents(events),
    renderNewsList(fed, "#fed-list", "#fed-status", { limit: 5, label: "聯準會發言" }),
    renderBullets(summary, "#summary-list", "global"),
    renderBullets(summary, "#support-list", "support"),
  ];
  setGlobalMeta(updated, status);
  renderSourceStatus(status);
}

function guessSession() {
  try {
    const tw = new Date(new Date().toLocaleString("en-US", { timeZone: "Asia/Taipei" }));
    const h = tw.getHours();
    if (h < 8) return "台股開盤前整理時段";
    if (h < 13) return "台股盤中";
    if (h < 21) return "美股開盤前整理時段";
    return "美股盤中 / 夜間";
  } catch { return "一般時段"; }
}

main();
