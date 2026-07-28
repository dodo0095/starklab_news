# StarkLab News — 個股資訊整合平台（MVP）

> **交接說明**（2026-07-28 更新）  
> 本文記錄「目前已完成什麼、怎麼跑、交接要注意什麼」。  
> 需求與範圍見 [`docs/重新規劃_v3.md`](docs/重新規劃_v3.md)、改進方向見 [`docs/改進建議.md`](docs/改進建議.md)。  
> 日常操作細節見 [`docs/使用手冊.md`](docs/使用手冊.md)。

**本機專案路徑：** `C:\Users\AUSER\Desktop\starklab_news`  
**遠端：** `https://github.com/dodo0095/starklab_news.git`

---

## 產品一句話

不想花時間整理資訊 — 把**市場總覽、重大新聞、河流圖**自動更新、一站呈現。  
更新時點：每天 **4 次** — **04:00**（美股收盤後）、**08:00**（台股開盤前）、**14:00**（台股收盤後）、**20:00**（美股開盤前）。

---

## 今天做了什麼（交接摘要）

### 1. 已完成功能

| 區塊 | 完成內容 |
|------|----------|
| 靜態網頁 | `index.html` + `css/style.css` + `js/app.js`（RWD，格子化版面，**每 10 分鐘自動重載**） |
| 市場總覽 | **美股/國際**（道瓊/納指/S&P500/台積ADR）+ **台股**（加權/櫃買/0050/台積電）兩排；含**台積電 ADR 溢價/折價**；紅漲綠跌 |
| ⭐ 本益比/淨值比河流圖 | 主角：歷史 PE/PB 分位切 6 條倍數線、色帶包住月均價；**PE↔PB 切換**、**輸入代碼查觀察名單**（2330/2317/2454/2308）、落點「怎麼看」白話說明 |
| 消息面熱度指針 | 情緒溫度計（新聞情緒＋大盤動能＋消息量＋Fed傾向）0–100，ECharts 半圓儀表 |
| 重大新聞 | 前五大（中文 RSS，已濾除「盤中速報」雜訊）+ **TSMC 個股專區** + **聯準會發言**（鷹/鴿標記） |
| 關注事件 | 非農等條件顯示（窗口內才出現） |
| 訊號聯動 | 估值高檔＋情緒偏熱 → 頂部雙訊號警示（低檔＋偏冷亦提示） |
| 防呆 | 無資料/讀取失敗/過期提示；示範資料標紅「非真實股價」；**排程心跳**顯示最後更新與各來源 ✓/✗ |

### 2. 資料管線（Python → JSON → 網頁）

架構刻意做**資料與畫面分離**，無 Django、無資料庫、無登入：

```
排程 / 手動執行 Python
        ↓
   data/*.json
        ↓
  瀏覽器靜態頁讀 JSON 繪製
```

| 腳本 | 產出 | 資料來源 |
|------|------|----------|
| `fetch_market.py` | `market.json`（美股+台股+ADR溢價） | yfinance |
| `fetch_news.py` | `news.json`（前五大，中文） | Google 新聞 zh-TW RSS |
| `fetch_tsmc_news.py` | `tsmc_news.json`（台積電專區） | Google 新聞 zh-TW |
| `fetch_fed.py` | `fed.json`（聯準會，含鷹/鴿） | Google 新聞 zh-TW |
| `fetch_valuation.py` | `valuation_{代碼}.json` + `valuation.json` + `watchlist.json` | yfinance（股價/EPS/淨值）|
| `fetch_events.py` | `events.json`（非農等） | 腳本內建行事曆 |
| `fetch_heat.py` | `heat.json`（消息面熱度）| 讀上述 JSON 合成 |
| `fetch_stock_ma.py` | `stock_ma.json`（均線，P1 保留）| yfinance |
| `run_all.py` | 一次跑全部 + 寫 `status.json`（排程心跳）| — |
| `update_with_log.ps1` | 同上 + 寫入 `logs/` | 排程實際呼叫這個 |

**失敗容錯：** 單一腳本失敗不會覆寫該 JSON，網頁繼續顯示「上一次成功的資料」。
**金十決策：** 主線不用金十（無免費 API），改中文 RSS；詳見 [`docs/金十驗證結論.md`](docs/金十驗證結論.md)。

### 3. 金十資料源決策（重要）

已驗證並寫入 [`docs/金十驗證結論.md`](docs/金十驗證結論.md)：

- 金十**無穩定免費公開 API / RSS**；官方 API 需申請 secret-key  
- 免費引用頁已停用  
- **MVP 決策：主線不用金十**  
  - 報價 / 均線 → yfinance  
  - 新聞 → RSS  
- 金十列為 **P1**（有 Key 再接；畫面不必改，仍讀 `news.json`）

### 4. 本機排程與操作腳本

| 檔案 | 用途 |
|------|------|
| `scripts/register_tasks.ps1` | 註冊 4 個 Windows 工作：`StarkLabNews_0400/0800/1400/2000`（並清掉舊版 2100） |
| `scripts/update_with_log.ps1` | 更新資料並寫 `logs/update-YYYY-MM-DD.log` |
| `scripts/start_server.ps1` | 啟動本機靜態站（預設 port 8080） |

**排程：** 每天 4 次（04:00 / 08:00 / 14:00 / 20:00）自動執行 `run_all.py` 重抓全站真實資料。  
若換電腦或搬資料夾，需在新路徑**重跑** `register_tasks.ps1`。

### 5. UI / 設計

- 格子化儀表板版面；沉穩藍配色、台股紅漲綠跌  
- 本益比河流圖對齊業界（財報狗風格）：藍→粉倍數帶、暗紅月均價、現價標記  
- 版面規劃圖：[`docs/ui-layout-mockup.html`](docs/ui-layout-mockup.html)  

### 6. 文件

| 文件 | 給誰看 |
|------|--------|
| 本 README | 交接總覽：今天做了什麼 |
| `MVP需求規劃.md` | 原始一週規劃、P0/P1/P2 範圍 |
| `docs/使用手冊.md` | 每天怎麼開站、怎麼手動更新、怎麼看 log |
| `docs/排程設定.md` | 排程建立 / 刪除 / 驗證 |
| `docs/金十驗證結論.md` | 為何不用金十、日後怎麼接 |

---

## 資料更新（手動 / 自動排程）

> 更新只會重寫 `data/*.json`；網頁是讀 JSON 繪製，**更新後請在瀏覽器按 Ctrl+F5** 才看到新數字。
> 每支腳本失敗只保留該項上次成功資料，不影響其他區塊。

### A. 手動更新（想立刻更新、不等排程時）

**方式 1（推薦，會寫 log 方便查）：**
```powershell
cd C:\Users\AUSER\Desktop\starklab_news
powershell -ExecutionPolicy Bypass -File scripts\update_with_log.ps1
```

**方式 2（直接跑，輸出在螢幕）：**
```powershell
cd C:\Users\AUSER\Desktop\starklab_news
python scripts\run_all.py
```

兩者都會**一次更新全部**：市場、五大新聞、TSMC、本益比股價、事件、Fed、熱度。

**只更新單一項目**（例如只想重抓股價 / 河流圖）：
```powershell
python scripts\fetch_valuation.py     # 本益比河流圖（會印出「現價(收盤)=…」可核對）
python scripts\fetch_market.py        # 大盤 / 台積電 ADR
python scripts\fetch_news.py          # 美國重大新聞（中文）
python scripts\fetch_tsmc_news.py     # 台積電個股新聞
python scripts\fetch_fed.py           # 聯準會發言
python scripts\fetch_heat.py          # 消息面熱度（需先跑上面幾支）
```

> 換河流圖標的：`$env:STOCK_SYMBOL="2317.TW"; $env:STOCK_NAME="鴻海"; python scripts\fetch_valuation.py`

### B. 自動排程（每天 4 次，設定一次即可）

以**系統管理員**開啟 PowerShell，於專案根目錄執行一次：
```powershell
cd C:\Users\AUSER\Desktop\starklab_news
powershell -ExecutionPolicy Bypass -File scripts\register_tasks.ps1
```
會建立 4 個 Windows 工作排程（並自動清掉舊版 21:00）：

| 任務 | 時間 | 用途 |
|------|------|------|
| `StarkLabNews_0400` | 04:00 | 美股收盤後 |
| `StarkLabNews_0800` | 08:00 | 台股開盤前 |
| `StarkLabNews_1400` | 14:00 | 台股收盤後 |
| `StarkLabNews_2000` | 20:00 | 美股開盤前 |

每次觸發都執行 `run_all.py`，重抓真實資料並覆蓋。

**確認排程存在：**
```powershell
schtasks /Query /TN StarkLabNews_0400
schtasks /Query /TN StarkLabNews_0800
schtasks /Query /TN StarkLabNews_1400
schtasks /Query /TN StarkLabNews_2000
```

**確認有跑成功：** 看網頁頂部「最後更新」時間、底部各來源 ✓，或查 `logs\update-YYYY-MM-DD.log`（結尾 `exit=0`）。

> 電腦關機會錯過排程；已設 `StartWhenAvailable` 會擇機補跑，最穩仍是開機後手動跑一次方式 1。

---

## 接手後：3 分鐘跑起來

```powershell
cd C:\Users\AUSER\Desktop\starklab_news

# 首次：安裝依賴
pip install -r requirements.txt

# 更新資料（寫 data/*.json + logs）
powershell -ExecutionPolicy Bypass -File scripts\update_with_log.ps1

# 開網頁
powershell -ExecutionPolicy Bypass -File scripts\start_server.ps1
```

瀏覽器開：**http://localhost:8080/**  
（不要直接雙擊 `index.html`，`file://` 下 `fetch` 常被擋。）

### 確認排程還在

```powershell
schtasks /Query /TN StarkLabNews_0400
schtasks /Query /TN StarkLabNews_0800
schtasks /Query /TN StarkLabNews_1400
schtasks /Query /TN StarkLabNews_2000
```

若沒有：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_tasks.ps1
```

### 看有沒有自動更新成功

```
logs\update-YYYY-MM-DD.log
```

---

## 專案結構

```
starklab_news/
├── index.html              # 入口頁
├── css/style.css           # 版面與配色
├── js/app.js               # 讀 JSON、畫卡片與 ECharts 河流圖
├── data/
│   ├── market.json           # 美股+台股+ADR溢價
│   ├── news.json             # 前五大新聞（中文）
│   ├── tsmc_news.json        # 台積電專區
│   ├── fed.json              # 聯準會發言
│   ├── valuation.json        # 預設(2330)本益比/淨值比河流圖
│   ├── valuation_{代碼}.json  # 觀察名單各檔
│   ├── watchlist.json        # 可查詢標的清單
│   ├── events.json           # 條件事件（非農等）
│   ├── heat.json             # 消息面熱度
│   ├── summary.json          # 全球摘要/大盤支撐（手動維護）
│   ├── stock_ma.json         # 均線（P1保留）
│   └── status.json           # 排程心跳（最後更新/各來源成敗）
├── scripts/
│   ├── common.py             # 共用：路徑、寫 JSON、均線
│   ├── fetch_*.py            # 各資料抓取（market/news/tsmc/fed/valuation/events/heat/stock_ma）
│   ├── run_all.py            # 一次全跑 + 寫 status.json
│   ├── update_with_log.ps1   # 排程用（有 log）
│   ├── register_tasks.ps1    # 註冊 04:00 / 08:00 / 14:00 / 20:00
│   └── start_server.ps1      # 本機 HTTP server
├── docs/
│   ├── 使用手冊.md / 排程設定.md / 金十驗證結論.md
│   ├── 重新規劃_v3.md         # 需求範圍與決策
│   ├── 改進建議.md            # 後續改進清單
│   └── ui-layout-mockup.html  # 版面規劃圖
├── logs/                   # 排程日誌（內容不進版控）
├── requirements.txt
├── MVP需求規劃.md
└── README.md               # 本文件
```

---

## 驗收對照（相對原規劃）

### P0 保底 — 已完成

- [x] 網頁可開、RWD  
- [x] 市場總覽卡片  
- [x] 重大新聞前五大  
- [x] 河流圖（1 檔 + 至少 2 條均線；實際含 MA60）  
- [x] 無資料 / 過期防呆  
- [x] 可用手動 JSON / 腳本維運，不依賴後端服務  

### P0 加分 — 已完成大部分

- [x] 真實資料源（yfinance + RSS，非純假資料）  
- [x] Windows 排程每天 4 次 04:00 / 08:00 / 14:00 / 20:00（接手請再確認）  
- [x] 非農等條件事件區塊  
- [ ] 金十串接 → **刻意不做**，改備援（見驗證結論）  

### P1 — 已完成

- [x] 本益比 + **淨值比(PB)** 河流圖、PE↔PB 切換  
- [x] 多標的查詢（觀察名單 2330/2317/2454/2308）  
- [x] 消息面熱度指針、訊號聯動提示  
- [x] 聯準會發言（原「川普」改此）、全球摘要/大盤支撐（手動維護）  
- [x] 每 10 分鐘自動重載、排程心跳/最後更新顯示  

### 未做（P2 或之後）

- 深色模式、載入骨架動畫、TSMC/Fed 新聞自動摘要  
- 推播（Email/Line）、投信報告、YouTube 整理、AI 回測/找標股、自動下單  

原始優先順序細節見 `docs/重新規劃_v3.md`。

---

## 已知限制（接手請知情）

1. **新聞為 RSS 非編輯精選**：已濾除「盤中速報」等雜訊並做關鍵字加權，但仍非人工精選。  
7. **部分台股估值為近似**：yfinance 對少數台股（如 2308 台達電）缺季度財報，其本益比河流圖退回近似估值帶並於畫面標示「近似」。  
2. **非農 actual**：目前不會自動抓公布值，需之後接 API 或手改 `events.json`。  
3. **本機 server 要開著**才看得到網頁；排程只負責更新 JSON，不負責開站。  
4. **電腦關機會錯過排程**；設了 StartWhenAvailable，仍建議錯過時手動跑一次更新。  
5. **PowerShell 腳本**：請用 `-ExecutionPolicy Bypass -File ...` 執行；`register_tasks.ps1` 等為避免編碼問題，訊息以英文為主。  
6. **不構成投資建議**；資料源使用條款請自行遵守。

---

## 建議接手後第一件事

1. `pip install -r requirements.txt`，本機跑一次 `run_all.py` + 開站，確認畫面與 `data/*.json` 正常  
2. 查 `schtasks` 四個任務是否還在；不在就重跑 `register_tasks.ps1`  
3. 連續 2～3 個交易日看 `logs/`，確認 04:00 / 08:00 / 14:00 / 20:00 有跑  
4. 再決定下一優先：上伺服器 / 深色模式 / 新聞自動摘要 / 推播  

有問題先對：`docs/使用手冊.md` → 當日 `logs/update-*.log` → 各 `fetch_*.py`。

---

## 授權與免責

本專案僅供資訊整理與學習用途，**不構成任何投資建議或買賣依據**。
