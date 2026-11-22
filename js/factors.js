/**
 * 公路運輸係數載入、動態計算公式與「公路運輸係數庫」頁籤渲染模組。
 */

export const UNIT_LABELS = {
  tkm: { activityLabel: "載重（公噸）", formulaText: "最短距離 (km) × 載重 (公噸) × 係數 × 去回程倍率" },
  pkm: { activityLabel: "人數（人）", formulaText: "最短距離 (km) × 人數 × 係數 × 去回程倍率" },
  km: { activityLabel: "趟次（趟）", formulaText: "最短距離 (km) × 趟次 × 係數 × 去回程倍率" },
};

export async function loadRoadFactors() {
  const resp = await fetch("data/road_factors.json", { cache: "no-store" });
  if (!resp.ok) {
    throw new Error(`無法載入係數檔案（HTTP ${resp.status}）`);
  }
  return resp.json();
}

export function calculateEmission({ distanceKm, activityValue, coeNum, roundTrip }) {
  const dist = Number(distanceKm) || 0;
  const act = Number(activityValue) || 0;
  const coe = Number(coeNum) || 0;
  const multiplier = roundTrip ? 2 : 1;
  return dist * act * coe * multiplier;
}

export function initFactorsTab(payload) {
  const factors = payload.factors || [];
  const groups = payload.metadata?.groups || [];
  const pillsEl = document.getElementById("factor-group-pills");
  const searchEl = document.getElementById("factor-search");
  const tbodyEl = document.getElementById("factors-table-body");
  const metaHintEl = document.getElementById("factors-meta-hint");

  if (metaHintEl && payload.metadata) {
    metaHintEl.textContent = `資料來源：環境部 CFP_P_02（共 ${factors.length} 筆｜同步於 ${payload.metadata.synced_at}）`;
  }

  let selectedGroup = "ALL";

  function renderPills() {
    if (!pillsEl) return;
    const allGroups = ["ALL", ...groups];
    pillsEl.innerHTML = allGroups
      .map((g) => {
        const label = g === "ALL" ? `全部 (${factors.length})` : g;
        const active = g === selectedGroup ? "active" : "";
        return `<button type="button" class="filter-pill ${active}" data-group="${escapeHtml(g)}">${escapeHtml(label)}</button>`;
      })
      .join("");

    pillsEl.querySelectorAll(".filter-pill").forEach((btn) => {
      btn.addEventListener("click", () => {
        selectedGroup = btn.dataset.group || "ALL";
        renderPills();
        renderTable();
      });
    });
  }

  function renderTable() {
    if (!tbodyEl) return;
    const kw = (searchEl?.value || "").trim().toLowerCase();
    const filtered = factors.filter((item) => {
      const matchGroup = selectedGroup === "ALL" || item.road_group === selectedGroup;
      if (!matchGroup) return false;
      if (!kw) return true;
      return (
        item.name.toLowerCase().includes(kw) ||
        item.road_group.toLowerCase().includes(kw) ||
        item.unit.toLowerCase().includes(kw)
      );
    });

    if (filtered.length === 0) {
      tbodyEl.innerHTML = `<tr><td colspan="7">查無符合條件的公路運輸係數。</td></tr>`;
      return;
    }

    tbodyEl.innerHTML = filtered
      .map((item) => {
        const vehicleBadge =
          item.default_vehicle === "機車"
            ? `<span class="badge badge-moto">機車</span>`
            : `<span class="badge badge-car">汽車</span>`;
        const formulaInfo = UNIT_LABELS[item.unit_type] || UNIT_LABELS.km;
        return `
          <tr>
            <td>${escapeHtml(item.road_group)}</td>
            <td><strong>${escapeHtml(item.name)}</strong></td>
            <td class="num-cell">${escapeHtml(String(item.coe))}</td>
            <td><span class="badge badge-unit">${escapeHtml(item.unit)}</span></td>
            <td>${escapeHtml(item.announcement_year || "—")}</td>
            <td>${vehicleBadge}</td>
            <td style="font-size: 0.78rem; color: var(--text-muted);">${escapeHtml(formulaInfo.formulaText)}</td>
          </tr>
        `;
      })
      .join("");
  }

  searchEl?.addEventListener("input", renderTable);
  renderPills();
  renderTable();
}

export function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
