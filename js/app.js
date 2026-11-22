import { loadRoadFactors, initFactorsTab } from "./factors.js";
import { initSingleTab } from "./single.js";
import { initBatchTab } from "./batch.js";

const LOCAL_ENGINE_BASE = "http://127.0.0.1:8787";

function initTabs() {
  const buttons = document.querySelectorAll(".tab-btn");
  const panels = document.querySelectorAll(".tab-panel");

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tab;
      buttons.forEach((b) => {
        const isActive = b === btn;
        b.classList.toggle("active", isActive);
        b.setAttribute("aria-selected", String(isActive));
      });
      panels.forEach((p) => {
        p.classList.toggle("active", p.id === `tab-${target}`);
      });
    });
  });
}

async function checkLocalEngineHealth() {
  const dotEl = document.getElementById("kpi-engine-dot");
  const textEl = document.getElementById("kpi-engine-text");
  if (!dotEl || !textEl) return;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 1800);

  try {
    const resp = await fetch(`${LOCAL_ENGINE_BASE}/health`, {
      signal: controller.signal,
      cache: "no-store",
    });
    if (resp.ok) {
      dotEl.className = "engine-dot online";
      textEl.textContent = "已連線";
      return;
    }
    throw new Error("Non-200");
  } catch {
    dotEl.className = "engine-dot offline";
    textEl.textContent = "未啟動";
  } finally {
    clearTimeout(timer);
  }
}

async function bootstrap() {
  initTabs();
  checkLocalEngineHealth();
  setInterval(checkLocalEngineHealth, 15000);

  try {
    const payload = await loadRoadFactors();
    const countEl = document.getElementById("kpi-factor-count");
    if (countEl) {
      countEl.textContent = `${payload.factors?.length || 0} 筆（9 類）`;
    }
    initSingleTab(payload);
    initBatchTab();
    initFactorsTab(payload);
  } catch (err) {
    const countEl = document.getElementById("kpi-factor-count");
    if (countEl) {
      countEl.textContent = "載入失敗";
    }
    console.error("Bootstrap error:", err);
  }
}

document.addEventListener("DOMContentLoaded", bootstrap);
