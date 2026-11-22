"""Google Maps 最短路徑鎖定與原生截圖核心引擎（Playwright）。"""

from __future__ import annotations

import asyncio
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError, async_playwright

VehicleMode = Literal["汽車", "機車"]

TZ_UTC8 = timezone(timedelta(hours=8))
INVALID_FILENAME_CHARS_RE = re.compile(r'[\\/:*?"<>|\s]+')
DIST_KM_RE = re.compile(r"([\d,.]+)\s*(公里|km)\b", re.IGNORECASE)
DIST_M_RE = re.compile(r"([\d,.]+)\s*(公尺|m)\b", re.IGNORECASE)
DURATION_RE = re.compile(
    r"(?:\d+\s*小時\s*)?\d+\s*分(?:鐘)?|\d+\s*hr(?:\s*\d+\s*min)?|\d+\s*min",
    re.IGNORECASE,
)
TRIP_CARD_SELECTOR = 'div[id^="section-directions-trip-"], div[data-trip-index]'


@dataclass
class RouteResult:
    """單筆路線查詢與截圖結果（Single Source of Truth）。"""

    ok: bool
    origin: str
    destination: str
    vehicle: str
    distance_km: float | None = None
    duration_text: str = ""
    route_summary: str = ""
    candidate_count: int = 0
    gmaps_url: str = ""
    screenshot_path: str = ""
    timestamp_utc8: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def now_utc8_str() -> str:
    return datetime.now(TZ_UTC8).strftime("%Y-%m-%d %H:%M:%S")


def sanitize_label(text: str, max_len: int = 12) -> str:
    """清洗檔名片段：移除非法字元並截斷至前 max_len 字。"""
    cleaned = INVALID_FILENAME_CHARS_RE.sub("", (text or "").strip())
    if not cleaned:
        return "未命名"
    return cleaned[:max_len]


def make_screenshot_filename(
    index: int,
    origin: str,
    destination: str,
    distance_km: float,
) -> str:
    """產出安全截圖檔名，例如：001_台積電F20P1_正美化工_10.8km.png。"""
    orig_part = sanitize_label(origin, 12)
    dest_part = sanitize_label(destination, 12)
    dist_str = f"{distance_km:.1f}".rstrip("0").rstrip(".") if distance_km == int(distance_km) else f"{distance_km:.1f}"
    return f"{index:03d}_{orig_part}_{dest_part}_{dist_str}km.png"


def parse_distance_km(text: str) -> float | None:
    """從路線卡片文字解析距離（公里）。優先匹配公里/km，其次公尺/m 除以 1000。"""
    if not text:
        return None
    km_match = DIST_KM_RE.search(text)
    if km_match:
        return float(km_match.group(1).replace(",", ""))
    m_match = DIST_M_RE.search(text)
    if m_match:
        return round(float(m_match.group(1).replace(",", "")) / 1000.0, 3)
    return None


def parse_trip_metadata(raw_text: str) -> tuple[float | None, str, str]:
    """從單張路線卡片文字抽取 (distance_km, duration_text, route_summary)。"""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    distance_km = parse_distance_km(raw_text)

    duration_text = ""
    for line in lines:
        m = DURATION_RE.search(line)
        if m:
            duration_text = m.group(0).strip()
            break

    route_summary = ""
    for line in lines:
        if line.startswith(("途經", "行經")) or "via " in line.lower():
            route_summary = line
            break
    if not route_summary and lines:
        # 退而取非純時間/距離的摘要行
        for line in lines:
            if not DIST_KM_RE.search(line) and not DIST_M_RE.search(line) and line != duration_text:
                route_summary = line
                break

    return distance_km, duration_text, route_summary


async def _accept_google_consent_if_present(page: Page) -> None:
    """若遇到 Google Consent / Cookie 同意畫面，自動點擊接受。"""
    if "consent.google" not in page.url:
        # 仍檢查頁面上是否有同意按鈕彈窗
        consent_selectors = [
            'button:has-text("全部接受")',
            'button:has-text("Accept all")',
            'button:has-text("我同意")',
        ]
    else:
        consent_selectors = [
            'button:has-text("全部接受")',
            'button:has-text("Accept all")',
            'button:has-text("I agree")',
            'form[action*="consent"] button[type="submit"]',
        ]

    for selector in consent_selectors:
        loc = page.locator(selector).first
        try:
            if await loc.is_visible(timeout=1200):
                await loc.click()
                await page.wait_for_timeout(1200)
                return
        except Exception:
            continue


async def _switch_vehicle_mode(page: Page, vehicle: VehicleMode, timeout_ms: int) -> None:
    """切換 Google Maps 車輛模式（汽車 / 機車）。"""
    target_mode = "9" if vehicle == "機車" else "0"
    tooltip_kw = "機車" if vehicle == "機車" else "開車"

    try:
        await page.wait_for_selector(
            f'[data-travel_mode="{target_mode}"] button, button[data-tooltip="{tooltip_kw}"]',
            state="attached",
            timeout=8000,
        )
    except PlaywrightTimeoutError:
        pass

    clicked = await page.evaluate(
        """({ mode, tooltip }) => {
            const containers = Array.from(document.querySelectorAll(`[data-travel_mode="${mode}"]`));
            for (const c of containers) {
                const btn = c.querySelector('button') || c;
                if (btn) {
                    btn.click();
                    return true;
                }
            }
            const byTooltip = document.querySelector(`button[data-tooltip="${tooltip}"], button[aria-label*="${tooltip}"]`);
            if (byTooltip) {
                byTooltip.click();
                return true;
            }
            return false;
        }""",
        {"mode": target_mode, "tooltip": tooltip_kw},
    )

    if not clicked:
        if vehicle == "機車":
            raise RuntimeError("無法在 Google Maps 頁面找到或切換至「機車」導航模式（該起訖點可能不支援機車路線）。")
        return

    await page.wait_for_timeout(2000)
    await page.wait_for_selector(TRIP_CARD_SELECTOR, timeout=min(timeout_ms, 12000))


async def _check_no_route_error(page: Page) -> str | None:
    """檢查頁面是否顯示查無路線或無法辨識地址。"""
    error_phrases = [
        "找不到路線",
        "無法規劃",
        "找不到",
        "Google 地圖找不到",
        "Sorry, we could not calculate directions",
        "can't find a way there",
    ]
    try:
        body_text = await page.locator('div[role="main"]').inner_text(timeout=2000)
    except Exception:
        return None

    for phrase in error_phrases:
        if phrase in body_text:
            return f"Google Maps 回報：{phrase}"
    return None


async def fetch_shortest_route_async(
    origin: str,
    destination: str,
    vehicle: VehicleMode,
    output_png: Path,
    timeout_ms: int = 30000,
    headless: bool = True,
) -> RouteResult:
    """非同步執行：開啟 Google Maps、切換汽機車、選取最短距離路線並截圖。"""
    origin_clean = (origin or "").strip()
    dest_clean = (destination or "").strip()
    if not origin_clean or not dest_clean:
        return RouteResult(
            ok=False,
            origin=origin_clean,
            destination=dest_clean,
            vehicle=vehicle,
            timestamp_utc8=now_utc8_str(),
            error="起點地址與終點地址不可為空。",
        )

    output_png = Path(output_png)
    output_png.parent.mkdir(parents=True, exist_ok=True)

    url = (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={quote(origin_clean)}"
        f"&destination={quote(dest_clean)}"
        "&travelmode=driving&hl=zh-TW"
    )

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                viewport={"width": 1366, "height": 820},
                locale="zh-TW",
                timezone_id="Asia/Taipei",
            )
            page = await context.new_page()
            page.set_default_timeout(timeout_ms)

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                await _accept_google_consent_if_present(page)

                # 等待路線清單或錯誤訊息出現
                try:
                    await page.wait_for_selector(
                        TRIP_CARD_SELECTOR,
                        timeout=timeout_ms,
                    )
                except PlaywrightTimeoutError:
                    err_msg = await _check_no_route_error(page)
                    return RouteResult(
                        ok=False,
                        origin=origin_clean,
                        destination=dest_clean,
                        vehicle=vehicle,
                        gmaps_url=page.url,
                        timestamp_utc8=now_utc8_str(),
                        error=err_msg or f"等待 Google Maps 路線載入逾時（{timeout_ms // 1000} 秒），請確認地址是否完整或網路連線正常。",
                    )

                # 切換指定車輛模式
                await _switch_vehicle_mode(page, vehicle, timeout_ms)

                # 讀取所有預設替代路線（不勾選避開高速公路），以 JS 一次抽取避免 DOM 重繪造成 locator 逾時
                raw_cards = await page.evaluate(
                    """() => {
                        const nodes = Array.from(
                            document.querySelectorAll('div[id^="section-directions-trip-"], div[data-trip-index]')
                        );
                        const seen = new Set();
                        const results = [];
                        for (const el of nodes) {
                            const id = el.getAttribute('id') || '';
                            const ti = el.getAttribute('data-trip-index');
                            const key = id || (ti !== null ? `ti:${ti}` : '');
                            if (!key || seen.has(key)) continue;
                            const text = (el.innerText || '').trim();
                            if (!text) continue;
                            seen.add(key);
                            results.push({ id, ti, text });
                        }
                        return results;
                    }"""
                )

                trip_entries: list[tuple[dict, float]] = []
                for card in raw_cards:
                    dist = parse_distance_km(card["text"])
                    if dist is not None:
                        trip_entries.append((card, dist))

                candidate_count = len(trip_entries)
                if candidate_count == 0:
                    err_msg = await _check_no_route_error(page)
                    return RouteResult(
                        ok=False,
                        origin=origin_clean,
                        destination=dest_clean,
                        vehicle=vehicle,
                        gmaps_url=page.url,
                        timestamp_utc8=now_utc8_str(),
                        error=err_msg or "未偵測到可解析距離的路線卡片。",
                    )

                # 選出距離最短之路線；若非預設第一條（已選中），才點擊切換鎖定，避免重複點擊已選中卡片而誤入詳細步驟頁
                min_card, _ = min(trip_entries, key=lambda item: item[1])
                first_card = trip_entries[0][0]
                if min_card["id"]:
                    target_sel = f'div#{min_card["id"]}'
                else:
                    target_sel = f'div[data-trip-index="{min_card["ti"]}"]'

                if min_card != first_card:
                    await page.evaluate(
                        """(sel) => {
                            const nodes = Array.from(document.querySelectorAll(sel));
                            const target = nodes.find(el => (el.innerText || '').trim().length > 0) || nodes[0];
                            if (target) target.click();
                        }""",
                        target_sel,
                    )
                    await page.wait_for_timeout(1500)

                # Single Source of Truth：從「已選取」路線 DOM 再次讀回最終確認數據
                final_text = await page.evaluate(
                    """(sel) => {
                        const nodes = Array.from(document.querySelectorAll(sel));
                        const target = nodes.find(el => (el.innerText || '').trim().length > 0) || nodes[0];
                        return target ? (target.innerText || '').trim() : '';
                    }""",
                    target_sel,
                )
                final_dist, duration_text, route_summary = parse_trip_metadata(final_text)
                if final_dist is None:
                    return RouteResult(
                        ok=False,
                        origin=origin_clean,
                        destination=dest_clean,
                        vehicle=vehicle,
                        candidate_count=candidate_count,
                        gmaps_url=page.url,
                        timestamp_utc8=now_utc8_str(),
                        error="點擊最短路線後無法讀回距離數值。",
                    )

                # 立即於完全相同畫面狀態下截圖
                await page.screenshot(path=str(output_png), full_page=False)

                return RouteResult(
                    ok=True,
                    origin=origin_clean,
                    destination=dest_clean,
                    vehicle=vehicle,
                    distance_km=final_dist,
                    duration_text=duration_text,
                    route_summary=route_summary,
                    candidate_count=candidate_count,
                    gmaps_url=page.url,
                    screenshot_path=str(output_png),
                    timestamp_utc8=now_utc8_str(),
                )
            finally:
                await context.close()
                await browser.close()

    except Exception as exc:
        return RouteResult(
            ok=False,
            origin=origin_clean,
            destination=dest_clean,
            vehicle=vehicle,
            timestamp_utc8=now_utc8_str(),
            error=str(exc),
        )


def fetch_shortest_route(
    origin: str,
    destination: str,
    vehicle: VehicleMode,
    output_png: Path,
    timeout_ms: int = 30000,
    headless: bool = True,
) -> RouteResult:
    """同步介面：在 CLI 或同步腳本中呼叫最短距離鎖定與截圖引擎。"""
    return asyncio.run(
        fetch_shortest_route_async(
            origin=origin,
            destination=destination,
            vehicle=vehicle,
            output_png=output_png,
            timeout_ms=timeout_ms,
            headless=headless,
        )
    )
