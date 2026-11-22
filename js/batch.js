import { escapeHtml } from "./factors.js";

const LOCAL_ENGINE_BASE = "http://127.0.0.1:8787";
const MAX_BATCH_ROWS = 20;

function formatTimestampForFile() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  return `${y}${m}${d}_${hh}${mm}`;
}

function triggerDownloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/**
 * 初始化「批次最短距離與截圖（≤20 筆）」頁籤。
 */
export function initBatchTab() {
  const templateBtn = document.getElementById("btn-download-template");
  const fileInput = document.getElementById("batch-file-input");
  const runBtn = document.getElementById("btn-batch-run");
  const zipBtn = document.getElementById("btn-batch-zip");
  const statusMsg = document.getElementById("batch-status-msg");
  const errorBox = document.getElementById("batch-error-box");
  const progressWrap = document.getElementById("batch-progress-wrap");
  const progressBar = document.getElementById("batch-progress-bar");
  const progressText = document.getElementById("batch-progress-text");
  const tbody = document.getElementById("batch-table-body");

  let batchRows = [];

  function showError(msg) {
    if (!errorBox) return;
    if (!msg) {
      errorBox.style.display = "none";
      errorBox.textContent = "";
    } else {
      errorBox.style.display = "block";
      errorBox.textContent = msg;
    }
  }

  function renderTable() {
    if (!tbody) return;
    if (batchRows.length === 0) {
      tbody.innerHTML = `<tr><td colspan="10">請先下載標準範本或上傳 Excel（.xlsx）檔案。</td></tr>`;
      return;
    }

    tbody.innerHTML = batchRows
      .map((row) => {
        const previewHtml = row.screenshot_base64
          ? `<img class="thumb-img" src="data:image/png;base64,${row.screenshot_base64}" alt="項次 ${row.index} 截圖">`
          : "—";
        const distText = row.distance_km != null ? `${row.distance_km}` : "—";
        const vehicleBadge =
          row.vehicle === "機車"
            ? `<span class="badge badge-moto">機車</span>`
            : `<span class="badge badge-car">汽車</span>`;
        return `
          <tr>
            <td class="num-cell">${escapeHtml(String(row.index))}</td>
            <td>${escapeHtml(row.origin)}</td>
            <td>${escapeHtml(row.destination)}</td>
            <td>${vehicleBadge}</td>
            <td class="num-cell">${escapeHtml(distText)}</td>
            <td>${escapeHtml(row.route_summary || "—")}</td>
            <td>${escapeHtml(row.duration_text || "—")}</td>
            <td class="num-cell">${row.candidate_count ?? "—"}</td>
            <td>${previewHtml}</td>
            <td>${escapeHtml(row.status || "待處理")}</td>
          </tr>
        `;
      })
      .join("");
  }

  templateBtn?.addEventListener("click", () => {
    showError("");
    if (!window.XLSX) {
      showError("SheetJS 尚未載入完成，請確認網路連線。");
      return;
    }

    const wb = window.XLSX.utils.book_new();
    const sampleRows = [
      ["項次", "起點地址", "終點地址", "車輛"],
      [1, "台積電F20P1 H2 308新竹縣寶山鄉大崎村科環路1號", "正美化工股份有限公司 300新竹市香山區", "汽車"],
      [2, "台北車站", "台北101", "機車"],
    ];
    const ws = window.XLSX.utils.aoa_to_sheet(sampleRows);
    ws["!cols"] = [{ wch: 8 }, { wch: 46 }, { wch: 42 }, { wch: 10 }];
    window.XLSX.utils.book_append_sheet(wb, ws, "批次路線範本");

    const guideRows = [
      ["欄位名稱", "填寫規範"],
      ["項次", "正整數編號（1~20）"],
      ["起點地址", "完整地址或明確地標名稱（不可為空）"],
      ["終點地址", "完整地址或明確地標名稱（不可為空）"],
      ["車輛", "僅限填「汽車」或「機車」"],
    ];
    const wsGuide = window.XLSX.utils.aoa_to_sheet(guideRows);
    window.XLSX.utils.book_append_sheet(wb, wsGuide, "填寫說明");

    window.XLSX.writeFile(wb, "陸地運輸最短距離批次範本.xlsx");
    if (statusMsg) statusMsg.textContent = "已下載標準 Excel 範本（含 2 筆台灣實測範例）。";
  });

  fileInput?.addEventListener("change", async (evt) => {
    showError("");
    const file = evt.target.files?.[0];
    if (!file) return;
    if (!window.XLSX) {
      showError("SheetJS 尚未載入完成，請確認網路連線。");
      return;
    }

    try {
      const buf = await file.arrayBuffer();
      const wb = window.XLSX.read(buf, { type: "array" });
      const firstSheet = wb.Sheets[wb.SheetNames[0]];
      const rawRows = window.XLSX.utils.sheet_to_json(firstSheet, { defval: "" });

      const parsed = [];
      for (let i = 0; i < rawRows.length; i += 1) {
        const r = rawRows[i];
        const orig = String(r["起點地址"] ?? "").trim();
        const dest = String(r["終點地址"] ?? "").trim();
        if (!orig && !dest) continue;

        const rawIndex = r["項次"];
        const idx = rawIndex !== "" && !Number.isNaN(Number(rawIndex)) ? Number(rawIndex) : parsed.length + 1;
        const vehicle = String(r["車輛"] ?? "").trim();

        if (!orig || !dest) {
          throw new Error(`第 ${i + 2} 列起點地址或終點地址為空。`);
        }
        if (vehicle !== "汽車" && vehicle !== "機車") {
          throw new Error(`第 ${i + 2} 列「車輛」值為「${vehicle}」，僅限填「汽車」或「機車」。`);
        }

        parsed.push({
          index: idx,
          origin: orig,
          destination: dest,
          vehicle,
          distance_km: null,
          route_summary: "",
          duration_text: "",
          candidate_count: null,
          screenshot_filename: "",
          screenshot_base64: "",
          gmaps_url: "",
          timestamp_utc8: "",
          status: "待處理",
        });
      }

      if (parsed.length === 0) {
        throw new Error("Excel 中未讀取到任何有效資料列，請確認欄位名稱為：項次、起點地址、終點地址、車輛。");
      }

      if (parsed.length > MAX_BATCH_ROWS) {
        batchRows = parsed;
        renderTable();
        if (runBtn) runBtn.disabled = true;
        if (zipBtn) zipBtn.disabled = true;
        throw new Error(`單次批次上限為 ${MAX_BATCH_ROWS} 筆，目前檔案共 ${parsed.length} 筆，已禁止送出，請分批處理。`);
      }

      batchRows = parsed;
      renderTable();
      if (statusMsg) statusMsg.textContent = `已載入「${file.name}」，共 ${batchRows.length} 筆有效路線，可開始執行批次抓取。`;
      if (runBtn) runBtn.disabled = false;
      if (zipBtn) zipBtn.disabled = true;
    } catch (err) {
      showError(err?.message || "解析 Excel 失敗。");
      if (runBtn) runBtn.disabled = true;
    } finally {
      fileInput.value = "";
    }
  });

  runBtn?.addEventListener("click", async () => {
    if (batchRows.length === 0 || batchRows.length > MAX_BATCH_ROWS) return;
    showError("");
    runBtn.disabled = true;
    if (zipBtn) zipBtn.disabled = true;
    if (progressWrap) progressWrap.style.display = "block";

    const total = batchRows.length;
    for (let i = 0; i < total; i += 1) {
      const row = batchRows[i];
      if (progressBar) progressBar.style.width = `${Math.round((i / total) * 100)}%`;
      if (progressText) progressText.textContent = `正在處理第 ${i + 1} / ${total} 筆（項次 ${row.index}）...`;

      row.status = "抓取中...";
      renderTable();

      try {
        const resp = await fetch(`${LOCAL_ENGINE_BASE}/api/route`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            origin: row.origin,
            destination: row.destination,
            vehicle: row.vehicle,
            index: row.index,
          }),
        });
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}`);
        }
        const data = await resp.json();
        if (data.ok) {
          row.distance_km = data.distance_km;
          row.route_summary = data.route_summary;
          row.duration_text = data.duration_text;
          row.candidate_count = data.candidate_count;
          row.screenshot_filename = data.screenshot_filename;
          row.screenshot_base64 = data.screenshot_base64;
          row.gmaps_url = data.gmaps_url;
          row.timestamp_utc8 = data.timestamp_utc8;
          row.status = "成功";
        } else {
          row.timestamp_utc8 = data.timestamp_utc8 || "";
          row.status = `失敗：${data.error || "未知錯誤"}`;
        }
      } catch (err) {
        row.status =
          err?.name === "TypeError"
            ? "失敗：無法連線本機引擎 (127.0.0.1:8787)"
            : `失敗：${err?.message || "連線錯誤"}`;
      }

      renderTable();
    }

    if (progressBar) progressBar.style.width = "100%";
    const okCount = batchRows.filter((r) => r.status === "成功").length;
    if (progressText) progressText.textContent = `批次完成：成功 ${okCount} 筆，失敗 ${total - okCount} 筆。`;
    if (statusMsg) statusMsg.textContent = `批次執行完畢（${okCount}/${total} 筆成功），可點擊「一鍵匯出批次 ZIP」。`;

    runBtn.disabled = false;
    if (zipBtn) zipBtn.disabled = false;
  });

  zipBtn?.addEventListener("click", async () => {
    if (batchRows.length === 0) return;
    if (!window.XLSX || !window.JSZip) {
      showError("前端打包函式庫（SheetJS / JSZip）尚未載入完成。");
      return;
    }

    const ts = formatTimestampForFile();
    const excelFilename = `陸地運輸最短距離結果_${ts}.xlsx`;

    const wb = window.XLSX.utils.book_new();
    const aoa = [
      [
        "項次",
        "起點地址",
        "終點地址",
        "車輛",
        "最短距離(km)",
        "採用路線",
        "預估時間",
        "替代路線數",
        "對應截圖檔名",
        "Google Maps 連結",
        "抓取時間(UTC+8)",
        "狀態",
      ],
      ...batchRows.map((r) => [
        r.index,
        r.origin,
        r.destination,
        r.vehicle,
        r.distance_km ?? "",
        r.route_summary || "",
        r.duration_text || "",
        r.candidate_count ?? "",
        r.screenshot_filename || "",
        r.gmaps_url || "",
        r.timestamp_utc8 || "",
        r.status || "",
      ]),
    ];

    const ws = window.XLSX.utils.aoa_to_sheet(aoa);
    window.XLSX.utils.book_append_sheet(wb, ws, "最短距離結果");
    const xlsxArray = window.XLSX.write(wb, { bookType: "xlsx", type: "array" });

    const zip = new window.JSZip();
    zip.file(excelFilename, xlsxArray);
    const shotsFolder = zip.folder("screenshots");
    for (const r of batchRows) {
      if (r.screenshot_base64 && r.screenshot_filename) {
        shotsFolder.file(r.screenshot_filename, r.screenshot_base64, { base64: true });
      }
    }

    const blob = await zip.generateAsync({ type: "blob" });
    triggerDownloadBlob(blob, `陸地運輸最短距離結果_${ts}.zip`);
  });
}
