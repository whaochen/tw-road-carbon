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

async function queryLocalNetworkPermission() {
  if (!navigator.permissions?.query) return "unknown";
  try {
    const res = await navigator.permissions.query({ name: "local-network-access" });
    return res.state || "unknown";
  } catch {
    return "unknown";
  }
}

async function checkLocalEngineHealth() {
  const dotEl = document.getElementById("kpi-engine-dot");
  const textEl = document.getElementById("kpi-engine-text");
  const hintEl = document.getElementById("kpi-engine-hint");
  if (!dotEl || !textEl) return false;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 1800);

  try {
    const resp = await fetch(`${LOCAL_ENGINE_BASE}/health`, {
      signal: controller.signal,
      cache: "no-store",
      targetAddressSpace: "local",
    });
    if (resp.ok) {
      dotEl.className = "engine-dot online";
      textEl.textContent = "已連線";
      hintEl?.classList.add("hidden");
      return true;
    }
    throw new Error("Non-200");
  } catch {
    const permState = await queryLocalNetworkPermission();
    dotEl.className = "engine-dot offline";
    if (permState === "denied") {
      textEl.textContent = "權限遭封鎖";
      if (hintEl) {
        hintEl.textContent = "⚙ 點此排除";
        hintEl.classList.remove("hidden");
      }
    } else {
      textEl.textContent = "未啟動";
      if (hintEl) {
        hintEl.textContent = "↻ 點擊重連";
        hintEl.classList.remove("hidden");
      }
    }
    return false;
  } finally {
    clearTimeout(timer);
  }
}

function initEngineStatusModal() {
  const statusBtn = document.getElementById("btn-engine-status");
  const modal = document.getElementById("engine-help-modal");
  const closeBtn = document.getElementById("btn-close-engine-modal");
  const retryBtn = document.getElementById("btn-modal-retry");
  const textEl = document.getElementById("kpi-engine-text");

  if (!statusBtn || !modal) return;

  function openModal() {
    modal.hidden = false;
  }

  function closeModal() {
    modal.hidden = true;
  }

  statusBtn.addEventListener("click", async () => {
    if (textEl) textEl.textContent = "偵測中...";
    const ok = await checkLocalEngineHealth();
    if (!ok) {
      openModal();
    }
  });

  retryBtn?.addEventListener("click", async () => {
    retryBtn.disabled = true;
    retryBtn.textContent = "偵測中...";
    const ok = await checkLocalEngineHealth();
    retryBtn.disabled = false;
    retryBtn.textContent = "立即重新偵測";
    if (ok) {
      closeModal();
    }
  });

  closeBtn?.addEventListener("click", closeModal);
  modal.addEventListener("click", (evt) => {
    if (evt.target === modal) closeModal();
  });
  document.addEventListener("keydown", (evt) => {
    if (evt.key === "Escape" && !modal.hidden) closeModal();
  });
}

async function bootstrap() {
  initTabs();
  initEngineStatusModal();
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
