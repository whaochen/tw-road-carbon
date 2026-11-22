# 臺灣陸地運輸GHG排放計算器（`tw-road-carbon`）

> 晧脈元素庫 `Cr · 24`（Chromium）｜線上網址：https://tw-road-carbon.pages.dev/

串接環境部公路運輸 9 大類碳足跡係數與 Google Maps 最短距離原生截圖，支援**單筆 GHG 試算**與 **20 筆批次 ZIP 查證匯出**，無需支付 Google Maps API 費用。

---

## 快速上手（3 步驟）

### 第 1 步：安裝 Python 與下載工具包（只需做一次）
1. 確認電腦已安裝 [Python 3.10+](https://www.python.org/downloads/)（安裝時請勾選 **`Add Python to PATH`**）。
2. 下載本專案壓縮檔：[點此下載 ZIP](https://github.com/whaochen/tw-road-carbon/archive/refs/heads/main.zip) 並解壓縮。

### 第 2 步：啟動本機截圖小幫手
1. 進入解壓後的 `engine/` 資料夾，雙擊 **`一鍵啟動本機引擎.bat`**。
2. 第一次執行會自動建立虛擬環境並下載 Playwright Chromium（約 1～2 分鐘）。
3. 看到視窗顯示 **「本機截圖小幫手已就緒」** 後，將視窗**縮小**即可（使用期間請勿關閉）。

### 第 3 步：開始計算與匯出 ZIP
- 開啟線上版 https://tw-road-carbon.pages.dev/ 或直接開啟本機版 `http://127.0.0.1:8787/`。
- **單筆試算**：輸入起點與終點、選擇環境部係數與活動數據 → 取得最短距離、GHG 排放量與原生截圖，並可一鍵匯出單筆 ZIP。
- **批次處理（≤20 筆）**：下載標準 Excel 範本填寫後上傳，即可逐筆抓取並匯出含結果 Excel 與 `screenshots/` 的完整 ZIP。

> **小技巧（免開網頁離線批次）**：也可直接將填好的 `.xlsx` 檔案拖曳至 `engine/一鍵啟動本機引擎.bat` 圖示上放開，程式會自動跑完並在同目錄產出 ZIP。
