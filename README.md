# StarkLab News — 個股資訊整合平台（MVP）

> **交接說明**（2026-07-27）  
> 本文記錄「今天已完成什麼、怎麼跑、交接要注意什麼」。  
> 原始需求規劃見 [`MVP需求規劃.md`](./MVP需求規劃.md)。  
> 日常操作細節見 [`docs/使用手冊.md`](docs/使用手冊.md)。

**本機專案路徑：** `C:\Users\AUSER\Desktop\starklab_news`  
**遠端：** `https://github.com/dodo0095/starklab_news.git`

---

## 產品一句話

不想花時間整理資訊 — 把**市場總覽、重大新聞、河流圖**自動更新、一站呈現。  
目標時點：每天 **08:00**（台股開盤前）、**21:00**（美股開盤前）。

---

## 今天做了什麼（交接摘要）

### 1. 從零做出可 Demo 的 MVP

| 區塊 | 完成內容 |
|------|----------|
| 靜態網頁 | `index.html` + `css/style.css` + `js/app.js`（RWD，Pico + 自訂樣式） |
| 市場總覽 | 道瓊 / 納斯達克 / S&P 500 / 台積電 ADR，漲跌色（台股習慣：紅漲綠跌） |
| 重大新聞 | 前五大標題 + 摘要 + 來源連結 |
| 河流圖 | 台積電 `2330.TW`，收盤 + MA5 / MA20 / MA60，ECharts 色帶 |
| 關注事件 | 非農等條件顯示（窗口內才出現） |
| 防呆 | 無資料 / 讀取失敗 / 資料超過約 36 小時顯示過期提示 |

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
| `scripts/fetch_market.py` | `data/market.json` | **yfinance** |
| `scripts/fetch_news.py` | `data/news.json` | Yahoo / BBC / Google News **RSS** |
| `scripts/fetch_stock_ma.py` | `data/stock_ma.json` | **yfinance**（預設 2330.TW） |
| `scripts/fetch_events.py` | `data/events.json` | 腳本內建行事曆（非即時抓數） |
| `scripts/run_all.py` | 一次跑上面全部 | — |
| `scripts/update_with_log.ps1` | 同上 + 寫入 `logs/` | 排程實際呼叫這個 |

**失敗容錯：** 單一腳本失敗不會覆寫該 JSON，網頁繼續顯示「上一次成功的資料」。

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
| `scripts/register_tasks.ps1` | 註冊 Windows 工作：`StarkLabNews_0800`、`StarkLabNews_2100` |
| `scripts/update_with_log.ps1` | 更新資料並寫 `logs/update-YYYY-MM-DD.log` |
| `scripts/start_server.ps1` | 啟動本機靜態站（預設 port 8080） |

**交接當日狀態：** 已在開發機註冊過 08:00 / 21:00 排程，並手動跑通更新（`exit=0`）。  
若換電腦或搬資料夾，需在新路徑**重跑** `register_tasks.ps1`。

### 5. UI 調整

- 壓掉 Pico 預設青綠「套版感」  
- 統一沉穩配色；河流圖線色一併調整  

### 6. 文件

| 文件 | 給誰看 |
|------|--------|
| 本 README | 交接總覽：今天做了什麼 |
| `MVP需求規劃.md` | 原始一週規劃、P0/P1/P2 範圍 |
| `docs/使用手冊.md` | 每天怎麼開站、怎麼手動更新、怎麼看 log |
| `docs/排程設定.md` | 排程建立 / 刪除 / 驗證 |
| `docs/金十驗證結論.md` | 為何不用金十、日後怎麼接 |

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
schtasks /Query /TN StarkLabNews_0800
schtasks /Query /TN StarkLabNews_2100
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
│   ├── market.json         # 大盤 / ADR
│   ├── news.json           # 前五大新聞
│   ├── stock_ma.json       # 河流圖用均線
│   └── events.json         # 條件事件（非農等）
├── scripts/
│   ├── common.py           # 共用：路徑、寫 JSON、均線
│   ├── fetch_*.py          # 各資料抓取
│   ├── run_all.py          # 一次全跑
│   ├── update_with_log.ps1 # 排程用（有 log）
│   ├── register_tasks.ps1  # 註冊 08:00 / 21:00
│   └── start_server.ps1    # 本機 HTTP server
├── docs/
│   ├── 使用手冊.md
│   ├── 排程設定.md
│   └── 金十驗證結論.md
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
- [x] Windows 排程 08:00 / 21:00（開發機已註冊；接手請再確認）  
- [x] 非農等條件事件區塊  
- [ ] 金十串接 → **刻意不做**，改備援（見驗證結論）  

### 未做（P1 / P2，非本階段承諾）

- 多檔股票切換 UI、推播（Email/Line）  
- 全球經濟摘要、川普發言整理  
- 投信報告、YouTube 整理、AI 回測/找標股、自動下單  

原始優先順序細節以 `MVP需求規劃.md` 為準。

---

## 已知限制（接手請知情）

1. **新聞品質不穩定**：RSS 有時偏個股推文；腳本有關鍵字加權，但非編輯精選。  
2. **非農 actual**：目前不會自動抓公布值，需之後接 API 或手改 `events.json`。  
3. **本機 server 要開著**才看得到網頁；排程只負責更新 JSON，不負責開站。  
4. **電腦關機會錯過排程**；設了 StartWhenAvailable，仍建議錯過時手動跑一次更新。  
5. **PowerShell 腳本**：請用 `-ExecutionPolicy Bypass -File ...` 執行；`register_tasks.ps1` 等為避免編碼問題，訊息以英文為主。  
6. **不構成投資建議**；資料源使用條款請自行遵守。

---

## 建議接手後第一件事

1. 本機跑一次更新 + 開站，確認畫面與 `data/*.json` 正常  
2. 查 `schtasks` 兩個任務是否還在；不在就重註冊  
3. 連續 2～3 個交易日看 `logs/`，確認 08:00 / 21:00 有跑  
4. 再決定下一優先：上伺服器 / 中文新聞源 / 多標的 / 推播  

有問題先對：`docs/使用手冊.md` → 當日 `logs/update-*.log` → 各 `fetch_*.py`。

---

## 授權與免責

本專案僅供資訊整理與學習用途，**不構成任何投資建議或買賣依據**。
