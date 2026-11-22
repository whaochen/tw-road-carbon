"""專案自動化驗證腳本（Phase 5）：字元鐵律、係數完整性、HTML 規範與引擎模組檢查。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
TEXT_EXTENSIONS = {".html", ".css", ".js", ".py", ".json", ".md", ".bat"}
REQUIRED_GROUPS = [
    "營業用大客車",
    "自用大客車",
    "貨車",
    "常溫貨車",
    "冷藏/凍貨車",
    "遊覽車",
    "小客車",
    "機車",
    "垃圾清運服務",
]


def verify_no_variant_hao() -> None:
    bad_files: list[str] = []
    for p in ROOT_DIR.rglob("*"):
        if ".venv" in p.parts or "__pycache__" in p.parts:
            continue
        if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS:
            txt = p.read_text(encoding="utf-8")
            if "\u7693" in txt:
                bad_files.append(str(p.relative_to(ROOT_DIR)))
    assert not bad_files, f"偵測到「晧」異體字 (U+7693)：{bad_files}"
    print("[PASS] 1. 全專案零異體字 (U+7693)，統一使用「晧」(U+6667)。")


def verify_road_factors() -> None:
    factors_path = ROOT_DIR / "data" / "road_factors.json"
    assert factors_path.exists(), f"找不到 {factors_path}"
    data = json.loads(factors_path.read_text(encoding="utf-8"))
    factors = data.get("factors", [])
    assert len(factors) > 0, "road_factors.json 係數筆數為 0"

    present_groups = {f.get("road_group") for f in factors}
    missing = [g for g in REQUIRED_GROUPS if g not in present_groups]
    assert not missing, f"缺少公路運輸子類：{missing}"

    for f in factors:
        assert f.get("name"), f"係數名稱為空：{f}"
        assert isinstance(f.get("coe_num"), (int, float)) and f["coe_num"] > 0, f"係數數值無效：{f}"
        assert f.get("unit"), f"宣告單位為空：{f}"
        assert f.get("default_vehicle") in ("汽車", "機車"), f"預設車輛模式無效：{f}"

    print(f"[PASS] 2. road_factors.json 涵蓋 9/9 公路運輸大類（共 {len(factors)} 筆有效係數）。")


def verify_index_html() -> None:
    html_path = ROOT_DIR / "index.html"
    html = html_path.read_text(encoding="utf-8")

    expected_title = "<title>臺灣陸地運輸GHG排放計算器 ｜ 晧脈元素庫</title>"
    assert expected_title in html, f"分頁標題不符合規範，預期：{expected_title}"
    assert "[24 Cr]" not in html, "標題禁止加上 [24 Cr] 前綴"

    badges = re.findall(r"<hao-element-badge\b[^>]*>", html)
    assert len(badges) == 1, f"應只有唯一一顆 hao-element-badge，目前：{len(badges)}"
    assert 'symbol="Cr"' in badges[0] and 'theme="dark"' in badges[0], f"badge 屬性不符：{badges[0]}"
    assert "https://hao-element-matrix.pages.dev/badge.js" in html, "未載入共用 badge.js"
    assert "ROAD · MRV SHORTEST PATH" in html, "缺少右側動畫狀態膠囊"

    print("[PASS] 3. index.html 雙層旗艦 Banner、標題與 Cr 元素徽章規範驗證通過。")


def verify_engine_modules() -> None:
    sys.path.insert(0, str(ROOT_DIR))
    from engine.local_server import app  # noqa: F401
    from engine.batch_cli import MAX_BATCH_ROWS, _read_excel_rows  # noqa: F401
    from engine.gmaps_shortest import fetch_shortest_route, make_screenshot_filename  # noqa: F401

    assert MAX_BATCH_ROWS == 20
    assert make_screenshot_filename(1, "台積電F20P1", "正美化工", 10.8) == "001_台積電F20P1_正美化工_10.8km.png"
    print("[PASS] 4. engine/local_server.py、engine/batch_cli.py、engine/gmaps_shortest.py 模組匯入與核心工具檢查通過。")


def main() -> None:
    verify_no_variant_hao()
    verify_road_factors()
    verify_index_html()
    verify_engine_modules()
    print("\nALL PROJECT VERIFICATIONS PASSED!")


if __name__ == "__main__":
    main()
