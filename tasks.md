# 臺灣陸地運輸GHG排放計算器（`tw-road-carbon`）開發規格書 `TASKS.md`

> **專案代號**：`tw-road-carbon`（建議本機路徑：`D:\Projects\tw-road-carbon`）  
> **正式網址**：`https://tw-road-carbon.pages.dev/`  
> **晧脈元素庫定位**：`Cr · 24`（鉻，Chromium）｜第 4 週期過渡金屬運輸家族（繼 `Ti` 航空、`Fe` 軌道、`Zn` 航海之後的陸運拼圖）  
> **架構模式**：雙軌零 API 費架構（Cloudflare Pages 靜態前端＋快取檢視 ＋ 本機 Playwright 最短路徑截圖引擎／一鍵批次工具）  
> **用字鐵律**：全站 HTML / CSS / JS / Python / JSON / 註解一律使用「**晧**」（`U+6667`），嚴禁出現異體字（`U+7693`）。

---

## 一、系統核心目標與 MRV 一致性原則

1. **單筆查詢（頁籤 1）**：輸入起點地址、終點地址、選擇環境部「公路運輸」碳足跡係數（自動對應 Google Maps「汽車」或「機車」模式）與活動數據（載重／人數／趟次／去回程 ×2），即時產出**最短距離（km）**、**GHG 排放量（kgCO2e）**，並在網站上直接顯示 **Google Maps 原生最短路徑截圖**（不嵌入互動地圖 iframe），提供**一鍵匯出單筆 ZIP**（Excel 計算表＋對應截圖 `.png`）。
2. **批次匯入與 ZIP 匯出（頁籤 2，單次上限 20 筆）**：
   - 提供標準 `.xlsx` 範本下載，固定欄位：`項次`、`起點地址`、`終點地址`、`車輛`（限填 `汽車` 或 `機車`）。
   - 批次功能專注於「**純抓最短距離＋對應截圖**」，匯出單一 ZIP 壓縮檔，內含：
     - 結果 Excel（`.xlsx`）：含原欄位＋最短距離（km）＋採用路線說明＋行車時間＋候選路線數＋對應截圖檔名＋Google Maps 驗證網址＋抓取時間戳記（UTC+8）。
     - `screenshots/` 資料夾：按項次與里程命名之原生截圖（範例：`001_台積電F20P1_正美化工_10.8km.png`）。
3. **100% 數據與截圖一致原則（Single Source of Truth）**：
   - 程式開啟 Google Maps 路線頁並切換至指定車輛模式（汽車／機車）後，讀取左側所有預設替代路線，找出**公里數最短**的一條並**程式點擊選取**。
   - 待地圖深藍主路線與氣泡重繪完成後，**從「已選取」的該條路線 DOM 再次讀回公里數，並在完全相同的畫面狀態下立即截圖**，確保寫入 Excel 的公里數與截圖中深藍色選取路線的數字 100% 吻合。

---

## 二、資料來源與目錄結構規劃

### 1. 碳足跡係數來源（對接 `cfp-query-web`）
- 來源：`whaochen/cfp-query-web` 專案之環境部 `CFP_P_02` 資料集（對應 `https://cfp.moenv.gov.tw/WebPage/WebSites/CoefficientDB.aspx`）。
- 篩選條件：`服務類 > 運輸服務 > 公路運輸` 全部 9 大子類：
  1. 營業用大客車（導航預設：`汽車`）
  2. 自用大客車（導航預設：`汽車`）
  3. 貨車（導航預設：`汽車`）
  4. 常溫貨車（導航預設：`汽車`）
  5. 冷藏/凍貨車（導航預設：`汽車`）
  6. 遊覽車（導航預設：`汽車`）
  7. 小客車（導航預設：`汽車`）
  8. 機車（導航預設：`機車`）
  9. 垃圾清運服務（導航預設：`汽車`）
- 依宣告單位自動對應計算公式：
  - `延噸公里 (tkm)`：`排放量 = 最短距離 (km) × 載重 (公噸) × 係數 × (去回程 ? 2 : 1)`
  - `延人公里 (pkm)`：`排放量 = 最短距離 (km) × 人數 × 係數 × (去回程 ? 2 : 1)`
  - `公里 (km)`：`排放量 = 最短距離 (km) × 趟次 × 係數 × (去回程 ? 2 : 1)`

### 2. 建議專案目錄結構
```text
tw-road-carbon/
├── index.html                  # 主頁（雙層旗艦 Banner + 純白 4 頁籤家族版型）
├── css/
│   └── style.css               # 延續 Fe/Zn 家族風格（深海藍黑頁首 + 淺灰白主體 + 淡天藍摘要卡）
├── js/
│   ├── app.js                  # 頁籤切換、本機引擎連線偵測（127.0.0.1:8787）、狀態管理
│   ├── factors.js              # 載入 data/road_factors.json、動態計算公式與單位切換
│   ├── single.js               # 單筆查詢、截圖預覽、單筆 ZIP（SheetJS + JSZip）匯出
│   └── batch.js                # Excel 範本生成、上傳驗證（≤20 筆）、批次進度追蹤與 ZIP 打包
├── data/
│   └── road_factors.json       # 由腳本同步自環境部 CFP_P_02 之公路運輸 9 大類係數
├── engine/                     # 本機 Playwright 最短路徑引擎與一鍵批次工具
│   ├── gmaps_shortest.py       # 核心：Playwright 開啟 Google Maps、切換汽機車、點選最短路線並截圖
│   ├── local_server.py         # 輕量 FastAPI/HTTP 本機橋接服務（http://127.0.0.1:8787，CORS 允許 Pages）
│   ├── batch_cli.py            # 純本機 CLI 批次腳本（直接吃 Excel 產出 ZIP，免開網頁也能跑）
│   ├── requirements.txt        # playwright, openpyxl, fastapi, uvicorn
│   └── 一鍵啟動本機引擎.bat      # Windows 使用者雙擊即可啟動本機截圖引擎
├── scripts/
│   ├── sync_road_factors.py    # 同步環境部公路運輸 9 大類係數至 data/road_factors.json
│   └── verify_project.py       # 驗證 JSON 格式、零「晧」異體字、分頁標題與 badge 規範
└── TASKS.md
```

---

## 三、分階段開發任務清單

### Phase 1：專案初始化、係數同步與雙層旗艦 Banner UI
- [ ] 建立專案骨架與 `scripts/sync_road_factors.py`，抓取／同步環境部 `CFP_P_02` 公路運輸 9 大類係數至 `data/road_factors.json`（保留係數名稱、數值、宣告單位、年份、生命週期階段、子類別、預設 Google Maps 車輛模式）。
- [ ] 套用 **晧脈元素庫雙層旗艦 Banner 規範**與 `Fe`／`Zn` 運輸家族版型：
  - **分頁 `<title>`**：`臺灣陸地運輸GHG排放計算器 ｜ 晧脈元素庫`（禁止加 `[24 Cr]` 前綴，由 `badge.js` 自動注入 `Cr` SVG Favicon）。
  - **左側第一層**：`Cr · 24 · Chromium` 元素方塊（電光天藍 `#29b6f6` 主題框）＋主標題「臺灣陸地運輸GHG排放計算器」＋單行精簡副標；**嚴禁**在標題旁加上重複的「晧脈元素庫成員」膠囊。
  - **左側第二層**：4 張毛玻璃 KPI 數據卡（`公路係數筆數`、`支援導航模式：汽車／機車`、`批次上限：20 筆／次`、`本機引擎狀態燈號`）＋右側唯一一顆中央共用 `<hao-element-badge symbol="Cr" theme="dark"></hao-element-badge>`（載入 `https://hao-element-matrix.pages.dev/badge.js`），**嚴禁**保留舊版靜態返回按鈕。
  - **右側動畫區（260px–320px）**：左上角微型狀態膠囊 `ROAD · MRV SHORTEST PATH`，純 SVG＋CSS 繪製「多條候選道路網中，最短路徑亮起電光藍霓虹流光＋車輛光點行駛」動畫，並實作 `@media (prefers-reduced-motion: reduce)` 降級與行動裝置自動隱藏。
  - **主體 4 頁籤（純白頁籤列＋淺灰白主體＋淡天藍結果摘要卡）**：
    1. `單筆陸運試算`
    2. `批次最短距離與截圖（≤20 筆）`
    3. `公路運輸係數庫`
    4. `本機引擎與 MRV 說明`

### Phase 2：核心 Playwright 最短距離鎖定與截圖引擎（`engine/gmaps_shortest.py`）
- [ ] 實作 `fetch_shortest_route(origin: str, destination: str, vehicle: Literal["汽車", "機車"], output_png: Path) -> RouteResult`：
  1. 啟動 Chromium（視窗固定 `1366×820`、`locale="zh-TW"`、`timezone_id="Asia/Taipei"`），導航至 `https://www.google.com/maps/dir/?api=1&origin={origin}&destination={destination}&travelmode=driving&hl=zh-TW`。
  2. 若出現 Google Consent／Cookie 頁面自動點擊接受；等待路線面板載入。
  3. **車輛模式切換**：
     - `汽車`：點擊開車圖示（`data-travel_mode="0"` 或 `aria-label` 含 `開車`／`Driving`）。
     - `機車`：點擊機車圖示（`data-travel_mode="9"` 或 `aria-label` 含 `機車`／`Two-wheeler`／`Motorcycle`）。
  4. **比對預設替代路線（不勾選避開高速公路）**：
     - 抓取所有路線卡片 `div[id^="section-directions-trip-"]`。
     - 正規表示式解析距離：`([\d,.]+)\s*(公里|km)` 轉浮點數；`([\d,.]+)\s*(公尺|m)` 除以 1000 轉公里。
     - 選出 `distance_km` 最小者之索引 `min_idx`。
  5. **點擊最短路線＋單一資料源截圖**：
     - 點擊 `trips[min_idx]` 並等待 1.5 秒確認地圖深藍主路線與距離標籤重繪完成。
     - 重新從 `trips[min_idx]` 讀回最終確認之 `distance_km`、`duration_text`、`route_summary` 與當前頁面 URL。
     - 立即對整個視窗呼叫 `page.screenshot(path=output_png, full_page=False)`，確保左欄路線清單與右側深藍主路線圖完整入鏡。
  6. 實作檔名安全清洗函式 `make_screenshot_filename(index, origin, destination, distance_km)`：輸出如 `001_台積電F20P1_正美化工_10.8km.png`（去除 `\ / : * ? " < > |`、過長地址截斷前 12 字）。
  7. 實作例外處理：查無路線、地址模糊或逾時（30 秒）時回傳清楚錯誤訊息，批次模式不中斷後續項次，於 Excel 狀態欄標註失敗原因。

### Phase 3：單筆試算與批次匯入／ZIP 匯出功能
- [ ] **頁籤 1（單筆陸運試算）**：
  - 輸入起點地址、終點地址、選擇公路運輸係數（支援分類篩選與搜尋；選定後自動帶入對應的 `汽車`／`機車`，仍允許使用者手動覆蓋）。
  - 依係數單位動態顯示載重（公噸）／人數／趟次與「去回程（×2）」選項。
  - 點擊「抓取最短距離並試算」呼叫本機引擎 `POST http://127.0.0.1:8787/api/route`，回傳後於頁面顯示：
    - 淡天藍摘要卡：最短距離（km）、GHG 總排放量（kgCO2e）、採用係數與年份、採用路線說明、Google Maps 原路線直連。
    - **原生 Google Maps 截圖預覽區**（直接呈現引擎回傳之 PNG 截圖，不嵌互動地圖）。
    - **一鍵匯出單筆 ZIP**：前端以 SheetJS + JSZip 打包 `單筆陸運GHG試算_{日期}.xlsx` ＋ 該筆原生截圖 `.png`。
- [ ] **頁籤 2（批次匯入與 ZIP 匯出，每次上限 20 筆）**：
  - 「下載標準 Excel 範本（`.xlsx`）」按鈕：內建欄位 `項次`、`起點地址`、`終點地址`、`車輛`，並預填 2 筆台灣實測範例（含圖三之「台積電F20P1 H2 308新竹縣寶山鄉大崎村科環路1號」至「正美化工股份有限公司 300新竹市香山區」汽車案例）及 `車輛` 下拉選單驗證（`汽車,機車`）。
  - 上傳 `.xlsx` 後即時解析預覽表格並驗證：
    - 嚴格限制 `1 <= 筆數 <= 20`，超過 20 筆顯示紅字提醒並禁止送出。
    - 檢查空地址與非法車輛名稱。
  - 批次執行時逐筆呼叫本機引擎（或 SSE／輪詢進度條顯示 `正在處理第 X / N 筆...`），每完成一筆即時更新表格內之最短距離與縮圖預覽。
  - 全部完成後點擊「**一鍵匯出批次 ZIP**」，打包：
    - `陸地運輸最短距離結果_YYYYMMDD_HHMM.xlsx`（欄位：`項次`、`起點地址`、`終點地址`、`車輛`、`最短距離(km)`、`採用路線`、`預估時間`、`替代路線數`、`對應截圖檔名`、`Google Maps 連結`、`抓取時間(UTC+8)`、`狀態`）。
    - `screenshots/` 資料夾（內含按 `001_起點_終點_10.8km.png` 命名之全數截圖）。

### Phase 4：本機橋接服務與 Windows 一鍵工具封裝
- [ ] 實作 `engine/local_server.py`（FastAPI 監聽 `127.0.0.1:8787`）：
  - `GET /health`：回傳引擎狀態與 Playwright 版本，供網頁頂部 KPI 燈號即時偵測。
  - `POST /api/route`：執行單筆最短距離與截圖，回傳 JSON（含距離、路線摘要、時間與 Base64 PNG）。
  - CORS 明確允許 `https://tw-road-carbon.pages.dev` 與 `http://localhost:*`。
- [ ] 實作 `engine/batch_cli.py`：提供離線備援，直接拖曳 Excel 至批次檔即可在同目錄產出完整結果 ZIP。
- [ ] 撰寫 `engine/一鍵啟動本機引擎.bat`（自動檢查 Python venv、首次安裝依賴與 `playwright install chromium`、啟動本機服務並提示已連線）。

### Phase 5：自動化驗證與上線準備
- [ ] 撰寫 `scripts/verify_project.py`：
  - 掃描全專案所有文字檔，確認零異體字「`U+7693`」，全部統一為「晧（`U+6667`）」。
  - 驗證 `data/road_factors.json` 涵蓋環境部公路運輸 9 大類別且無空數值。
  - 驗證 `index.html` 符合 `<title>臺灣陸地運輸GHG排放計算器 ｜ 晧脈元素庫</title>` 與單一 `<hao-element-badge symbol="Cr" theme="dark">` 規範。
- [ ] 實測驗收：
  - 以圖三路線（台積電 F20P1 H2 → 正美化工，汽車）測試，確認自動從 14.5 km 改選並鎖定 **10.8 km**，且截圖畫面與匯出 Excel 數字皆為 `10.8`。
  - 測試同一組起訖點切換為 **機車** 模式，確認正確切換並鎖定機車最短距離。
  - 測試 3 筆批次匯入與 21 筆超限阻擋，確認 ZIP 內 Excel 與 `screenshots/` 圖片檔名與數據 100% 對應。

---

## 四、附錄：晧脈元素庫主站對接資料（待子站上線後寫入 `hao-element-matrix`）

```json
"Cr": {
  "shortName": "陸運碳排",
  "title": "臺灣陸地運輸GHG排放計算器",
  "subtitle": "Taiwan Road GHG",
  "description": "串接環境部公路運輸9大類係數與Google Maps最短距離原生截圖，支援單筆試算與20筆批次ZIP查證匯出。",
  "whyElement": "鉻是車體高強度合金與汽機車排氣系統核心元素，象徵公路運具碳排精準盤查。",
  "url": "https://tw-road-carbon.pages.dev/",
  "domainLabel": "tw-road-carbon.pages.dev",
  "status": "beta",
  "statusLabel": "BETA 測試中",
  "tags": ["環境部CFP", "最短距離", "批次截圖ZIP"],
  "emblemType": "default"
}
```
