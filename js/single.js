import { UNIT_LABELS, calculateEmission, escapeHtml } from "./factors.js";

const LOCAL_ENGINE_BASE = "http://127.0.0.1:8787";

function formatDateYYYYMMDD() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}${m}${d}`;
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
 * 初始化「單筆陸運試算」頁籤：本機引擎路線抓取、動態碳排試算與單筆 ZIP 匯出。
 */
export function initSingleTab(payload) {
  const factors = payload.factors || [];
  const groups = payload.metadata?.groups || [];

  const originInput = document.getElementById("single-origin");
  const destInput = document.getElementById("single-destination");
  const groupSelect = document.getElementById("single-group");
  const factorSelect = document.getElementById("single-factor");
  const vehicleSelect = document.getElementById("single-vehicle");
  const activityInput = document.getElementById("single-activity");
  const roundtripInput = document.getElementById("single-roundtrip");
  const activityLabel = document.getElementById("single-activity-label");
  const formulaHint = document.getElementById("single-formula-hint");
  const calcBtn = document.getElementById("btn-single-calc");
  const zipBtn = document.getElementById("btn-single-zip");

  const resDistanceEl = document.getElementById("res-distance");
  const resGhgEl = document.getElementById("res-ghg");
  const resFactorEl = document.getElementById("res-factor");
  const resRouteEl = document.getElementById("res-route");
  const resLinkWrap = document.getElementById("res-gmaps-link-wrap");
  const errorBox = document.getElementById("single-error-box");
  const screenshotBox = document.getElementById("single-screenshot-box");

  if (!groupSelect || !factorSelect) return;

  let lastResult = null;

  groupSelect.innerHTML =
    `<option value="">全部 9 大公路運輸類別（${factors.length} 筆）</option>` +
    groups.map((g) => `<option value="${escapeHtml(g)}">${escapeHtml(g)}</option>`).join("");

  function getSelectedFactor() {
    return factors.find((f) => f.id === factorSelect.value) || null;
  }

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

  function refreshEmissionDisplay() {
    if (!lastResult || !lastResult.ok) return;
    const factor = getSelectedFactor();
    if (!factor) return;

    const actVal = Number(activityInput?.value || 0);
    const roundTrip = Boolean(roundtripInput?.checked);
    const ghg = calculateEmission({
      distanceKm: lastResult.distance_km,
      activityValue: actVal,
      coeNum: factor.coe_num,
      roundTrip,
    });

    if (resGhgEl) resGhgEl.textContent = `${ghg.toFixed(4)} kgCO2e`;
    if (resFactorEl) {
      resFactorEl.textContent = `${factor.coe} kgCO2e/${factor.unit}（${factor.announcement_year || "—"}）`;
    }
  }

  function populateFactors() {
    const selectedGroup = groupSelect.value;
    const list = selectedGroup
      ? factors.filter((f) => f.road_group === selectedGroup)
      : factors;

    factorSelect.innerHTML = list
      .map(
        (f) =>
          `<option value="${escapeHtml(f.id)}">[${escapeHtml(f.road_group)}] ${escapeHtml(f.name)}（${escapeHtml(f.coe)} kgCO2e/${escapeHtml(f.unit)}，${escapeHtml(f.announcement_year)}）</option>`
      )
      .join("");

    syncFactorMeta();
  }

  function syncFactorMeta() {
    const current = getSelectedFactor();
    if (!current) return;

    if (vehicleSelect) {
      vehicleSelect.value = current.default_vehicle || "汽車";
    }
    const unitInfo = UNIT_LABELS[current.unit_type] || UNIT_LABELS.km;
    if (activityLabel) {
      activityLabel.textContent = unitInfo.activityLabel;
    }
    if (formulaHint) {
      formulaHint.textContent = `公式：${unitInfo.formulaText}`;
    }
    refreshEmissionDisplay();
  }

  groupSelect.addEventListener("change", populateFactors);
  factorSelect.addEventListener("change", syncFactorMeta);
  activityInput?.addEventListener("input", refreshEmissionDisplay);
  roundtripInput?.addEventListener("change", refreshEmissionDisplay);

  calcBtn?.addEventListener("click", async () => {
    const origin = (originInput?.value || "").trim();
    const destination = (destInput?.value || "").trim();
    const vehicle = vehicleSelect?.value === "機車" ? "機車" : "汽車";
    const factor = getSelectedFactor();

    showError("");
    if (!origin || !destination) {
      showError("請填寫完整的起點地址與終點地址。");
      return;
    }
    if (!factor) {
      showError("請選擇一項公路運輸碳足跡係數。");
      return;
    }

    calcBtn.disabled = true;
    calcBtn.textContent = "本機引擎抓取中...";
    if (zipBtn) zipBtn.disabled = true;
    if (screenshotBox) {
      screenshotBox.textContent = "正在啟動本機 Chromium 抓取最短距離並擷取 Google Maps 原生畫面，請稍候...";
    }

    try {
      const resp = await fetch(`${LOCAL_ENGINE_BASE}/api/route`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          origin,
          destination,
          vehicle,
          index: 1,
        }),
      });
      if (!resp.ok) {
        throw new Error(`本機引擎回應異常（HTTP ${resp.status}）`);
      }

      const data = await resp.json();
      if (!data.ok) {
        throw new Error(data.error || "路線抓取失敗，請確認地址是否完整。");
      }

      lastResult = data;
      if (resDistanceEl) resDistanceEl.textContent = `${data.distance_km} km`;
      if (resRouteEl) {
        const parts = [data.route_summary, data.duration_text].filter(Boolean);
        resRouteEl.textContent = parts.join(" · ") || "已鎖定最短路線";
      }
      if (resLinkWrap && data.gmaps_url) {
        resLinkWrap.innerHTML = `<a href="${escapeHtml(data.gmaps_url)}" target="_blank" rel="noopener">開啟 Google Maps 原路線驗證 ↗</a>`;
      }
      refreshEmissionDisplay();

      if (screenshotBox && data.screenshot_base64) {
        screenshotBox.innerHTML = `<img src="data:image/png;base64,${data.screenshot_base64}" alt="Google Maps 最短距離原生截圖">`;
      }
      if (zipBtn) zipBtn.disabled = false;
    } catch (err) {
      lastResult = null;
      const msg =
        err?.name === "TypeError"
          ? "無法連線至本機引擎（http://127.0.0.1:8787）。請先雙擊執行 engine/一鍵啟動本機引擎.bat。"
          : err?.message || "查詢失敗";
      showError(msg);
      if (screenshotBox) {
        screenshotBox.textContent = "尚未取得截圖，請確認本機引擎已啟動後重試。";
      }
    } finally {
      calcBtn.disabled = false;
      calcBtn.textContent = "抓取最短距離並試算";
    }
  });

  zipBtn?.addEventListener("click", async () => {
    if (!lastResult || !lastResult.ok) return;
    if (!window.XLSX || !window.JSZip) {
      showError("前端打包函式庫（SheetJS / JSZip）尚未載入完成，請確認網路連線後重試。");
      return;
    }

    const factor = getSelectedFactor();
    const actVal = Number(activityInput?.value || 0);
    const roundTrip = Boolean(roundtripInput?.checked);
    const ghg = calculateEmission({
      distanceKm: lastResult.distance_km,
      activityValue: actVal,
      coeNum: factor?.coe_num || 0,
      roundTrip,
    });

    const dateStr = formatDateYYYYMMDD();
    const xlsxName = `單筆陸運GHG試算_${dateStr}.xlsx`;
    const pngName = lastResult.screenshot_filename || `001_road_shortest_${lastResult.distance_km}km.png`;

    const wb = window.XLSX.utils.book_new();
    const rows = [
      [
        "起點地址",
        "終點地址",
        "車輛模式",
        "最短距離(km)",
        "活動數據",
        "去回程倍率",
        "係數名稱",
        "係數數值",
        "宣告單位",
        "公告年份",
        "GHG總排放量(kgCO2e)",
        "採用路線",
        "預估時間",
        "對應截圖檔名",
        "Google Maps連結",
        "抓取時間(UTC+8)",
      ],
      [
        lastResult.origin,
        lastResult.destination,
        lastResult.vehicle,
        lastResult.distance_km,
        actVal,
        roundTrip ? 2 : 1,
        factor?.name || "",
        factor?.coe_num || 0,
        factor?.unit || "",
        factor?.announcement_year || "",
        Number(ghg.toFixed(4)),
        lastResult.route_summary,
        lastResult.duration_text,
        pngName,
        lastResult.gmaps_url,
        lastResult.timestamp_utc8,
      ],
    ];
    const ws = window.XLSX.utils.aoa_to_sheet(rows);
    window.XLSX.utils.book_append_sheet(wb, ws, "單筆陸運GHG試算");
    const xlsxArray = window.XLSX.write(wb, { bookType: "xlsx", type: "array" });

    const zip = new window.JSZip();
    zip.file(xlsxName, xlsxArray);
    if (lastResult.screenshot_base64) {
      zip.file(pngName, lastResult.screenshot_base64, { base64: true });
    }
    const blob = await zip.generateAsync({ type: "blob" });
    triggerDownloadBlob(blob, `單筆陸運GHG試算_${dateStr}.zip`);
  });

  populateFactors();
}
