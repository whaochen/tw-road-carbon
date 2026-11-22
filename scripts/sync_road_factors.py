"""同步環境部 CFP_P_02 公路運輸 9 大類碳足跡係數至 data/road_factors.json。"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
OUTPUT_PATH = DATA_DIR / "road_factors.json"

LOCAL_CFP_FACTORS = Path(r"D:\Projects\cfp-query-web\data\cfp_factors.json")
LOCAL_CFP_DETAILS = Path(r"D:\Projects\cfp-query-web\data\cfp_details.json")
REMOTE_CFP_FACTORS_URL = (
    "https://raw.githubusercontent.com/whaochen/cfp-query-web/main/data/cfp_factors.json"
)

ROAD_GROUP_ORDER = [
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


def load_source_factors() -> tuple[list[dict[str, Any]], str]:
    """優先從本機 cfp-query-web 讀取，若不存在則從 GitHub 下載。"""
    if LOCAL_CFP_FACTORS.exists():
        with LOCAL_CFP_FACTORS.open("r", encoding="utf-8") as f:
            return json.load(f), str(LOCAL_CFP_FACTORS)

    req = urllib.request.Request(
        REMOTE_CFP_FACTORS_URL,
        headers={"User-Agent": "tw-road-carbon/1.0"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8")), REMOTE_CFP_FACTORS_URL


def load_lifecycle_map() -> dict[str, str]:
    """嘗試從 cfp_details.json 讀取生命週期階段（搖籃到大門／搖籃到墳墓等）。"""
    if not LOCAL_CFP_DETAILS.exists():
        return {}
    try:
        with LOCAL_CFP_DETAILS.open("r", encoding="utf-8") as f:
            details = json.load(f)
        if isinstance(details, dict):
            return {
                k: str(v.get("lifecycle_stage") or v.get("life_cycle") or "")
                for k, v in details.items()
                if isinstance(v, dict)
            }
        if isinstance(details, list):
            return {
                str(item.get("id")): str(item.get("lifecycle_stage") or item.get("life_cycle") or "")
                for item in details
                if isinstance(item, dict) and item.get("id")
            }
    except Exception:
        return {}
    return {}


def classify_road_group(record: dict[str, Any]) -> str | None:
    """將環境部 CFP_P_02 資料對應至公路運輸 9 大子類。"""
    name = str(record.get("name") or "")
    sub_cat = str(record.get("sub_category") or "")
    unit = str(record.get("unit") or "")

    # 1~6 類：具有明確 sub_category 標籤之公路運輸服務
    if sub_cat.startswith("公路運輸 / "):
        group = sub_cat.split("公路運輸 / ", 1)[1].strip()
        if group in ROAD_GROUP_ORDER:
            return group

    # 7. 小客車（早期公告可能無 sub_category）
    if "小客車" in name and unit in ("延人公里(pkm)", "公里(km)"):
        return "小客車"

    # 8. 機車（環境部名稱為「機器腳踏車(汽油)」等）
    if ("機器腳踏車" in name or "機車" in name) and unit in ("延人公里(pkm)", "公里(km)"):
        return "機車"

    # 9. 垃圾清運服務（以垃圾車清除運輸）
    if "垃圾車" in name and "清除運輸" in name and unit in ("延噸公里(tkm)", "公里(km)"):
        return "垃圾清運服務"

    return None


def parse_unit_type(unit: str) -> str:
    """依宣告單位對應計算公式類型：tkm / pkm / km。"""
    if "tkm" in unit or "延噸公里" in unit:
        return "tkm"
    if "pkm" in unit or "延人公里" in unit:
        return "pkm"
    return "km"


def main() -> None:
    raw_factors, source_ref = load_source_factors()
    lifecycle_map = load_lifecycle_map()

    road_items: list[dict[str, Any]] = []
    for rec in raw_factors:
        group = classify_road_group(rec)
        if not group:
            continue

        unit = str(rec.get("unit") or "").strip()
        coe_num = rec.get("coe_num")
        if coe_num is None:
            try:
                coe_num = float(rec.get("coe"))
            except (TypeError, ValueError):
                continue

        rec_id = str(rec.get("id") or "")
        default_vehicle = "機車" if group == "機車" else "汽車"
        lifecycle = (
            rec.get("lifecycle_stage")
            or rec.get("life_cycle")
            or lifecycle_map.get(rec_id)
            or "服務生命週期（依環境部公告邊界）"
        )

        road_items.append(
            {
                "id": rec_id,
                "name": str(rec.get("name") or "").strip(),
                "coe": str(rec.get("coe") or coe_num),
                "coe_num": float(coe_num),
                "unit": unit,
                "unit_type": parse_unit_type(unit),
                "department": str(rec.get("department") or "環境部").strip(),
                "announcement_year": str(rec.get("announcement_year") or "").strip(),
                "lifecycle_stage": str(lifecycle).strip(),
                "major_category": rec.get("major_category") or "服務類",
                "category": rec.get("category") or "運輸服務",
                "sub_category": rec.get("sub_category") or f"公路運輸 / {group}",
                "road_group": group,
                "default_vehicle": default_vehicle,
                "scope3_iso": rec.get("scope3_iso") or "",
                "scope3_ghg": rec.get("scope3_ghg") or "",
            }
        )

    # 依 9 大子類順序、公告年份由新到舊、名稱排序
    group_rank = {g: i for i, g in enumerate(ROAD_GROUP_ORDER)}
    road_items.sort(
        key=lambda x: (
            group_rank.get(x["road_group"], 99),
            -(int(x["announcement_year"]) if x["announcement_year"].isdigit() else 0),
            x["name"],
        )
    )

    present_groups = sorted(
        {item["road_group"] for item in road_items},
        key=lambda g: group_rank.get(g, 99),
    )

    tz_utc8 = timezone(timedelta(hours=8))
    payload = {
        "metadata": {
            "source": "環境部產品碳足跡資訊網 CFP_P_02（對接 whaochen/cfp-query-web）",
            "source_ref": source_ref,
            "synced_at": datetime.now(tz_utc8).strftime("%Y-%m-%d %H:%M:%S UTC+8"),
            "total_count": len(road_items),
            "group_count": len(present_groups),
            "groups": ROAD_GROUP_ORDER,
        },
        "factors": road_items,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Synced {len(road_items)} road transport factors across {len(present_groups)}/9 groups -> {OUTPUT_PATH}")
    for g in ROAD_GROUP_ORDER:
        cnt = sum(1 for item in road_items if item["road_group"] == g)
        print(f"  - {g}: {cnt}")


if __name__ == "__main__":
    main()
