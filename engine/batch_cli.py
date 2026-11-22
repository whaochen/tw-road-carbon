"""純本機 CLI 批次腳本：直接讀取 Excel（≤20 筆）產出含截圖與結果 Excel 之 ZIP。"""

from __future__ import annotations

import argparse
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from openpyxl import Workbook, load_workbook

from engine.gmaps_shortest import fetch_shortest_route, make_screenshot_filename

TZ_UTC8 = timezone(timedelta(hours=8))
MAX_BATCH_ROWS = 20
REQUIRED_COLUMNS = ("項次", "起點地址", "終點地址", "車輛")


def _read_excel_rows(excel_path: Path) -> list[dict]:
    wb = load_workbook(excel_path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Excel 檔案為空。")

    headers = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
    col_idx = {name: i for i, name in enumerate(headers) if name}
    missing = [col for col in REQUIRED_COLUMNS if col not in col_idx]
    if missing:
        raise ValueError(f"Excel 缺少必要欄位：{', '.join(missing)}")

    parsed: list[dict] = []
    for row_num, row in enumerate(rows[1:], start=2):
        orig = str(row[col_idx["起點地址"]] or "").strip()
        dest = str(row[col_idx["終點地址"]] or "").strip()
        if not orig and not dest:
            continue
        raw_idx = row[col_idx["項次"]]
        try:
            item_index = int(raw_idx) if raw_idx is not None else (len(parsed) + 1)
        except (TypeError, ValueError):
            item_index = len(parsed) + 1

        vehicle = str(row[col_idx["車輛"]] or "汽車").strip()
        if vehicle not in ("汽車", "機車"):
            raise ValueError(f"第 {row_num} 列「車輛」欄位無效（{vehicle}），僅限填「汽車」或「機車」。")
        if not orig or not dest:
            raise ValueError(f"第 {row_num} 列起點地址或終點地址不可為空。")

        parsed.append(
            {
                "index": item_index,
                "origin": orig,
                "destination": dest,
                "vehicle": vehicle,
            }
        )

    if not parsed:
        raise ValueError("Excel 中沒有任何有效資料列。")
    if len(parsed) > MAX_BATCH_ROWS:
        raise ValueError(f"單次批次上限為 {MAX_BATCH_ROWS} 筆，目前檔案共 {len(parsed)} 筆，請分批處理。")

    return parsed


def run_batch_cli(excel_path: Path, output_zip: Path | None = None) -> Path:
    excel_path = Path(excel_path).resolve()
    items = _read_excel_rows(excel_path)

    now_str = datetime.now(TZ_UTC8).strftime("%Y%m%d_%H%M")
    if output_zip is None:
        output_zip = excel_path.parent / f"陸地運輸最短距離結果_{now_str}.zip"
    else:
        output_zip = Path(output_zip).resolve()

    excel_filename = f"陸地運輸最短距離結果_{now_str}.xlsx"

    with tempfile.TemporaryDirectory(prefix="tw_road_cli_") as tmp_dir:
        tmp_root = Path(tmp_dir)
        shots_dir = tmp_root / "screenshots"
        shots_dir.mkdir(parents=True, exist_ok=True)

        wb_out = Workbook()
        ws_out = wb_out.active
        ws_out.title = "最短距離結果"
        ws_out.append(
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
            ]
        )

        shot_files: list[Path] = []
        total = len(items)
        for pos, item in enumerate(items, start=1):
            print(f"[{pos}/{total}] 處理項次 {item['index']}：{item['origin']} -> {item['destination']} ({item['vehicle']})")
            tmp_png = shots_dir / f"_tmp_{item['index']:03d}.png"
            res = fetch_shortest_route(
                origin=item["origin"],
                destination=item["destination"],
                vehicle=item["vehicle"],
                output_png=tmp_png,
            )

            shot_name = ""
            if res.ok and res.distance_km is not None and tmp_png.exists():
                shot_name = make_screenshot_filename(
                    index=item["index"],
                    origin=item["origin"],
                    destination=item["destination"],
                    distance_km=res.distance_km,
                )
                final_png = shots_dir / shot_name
                tmp_png.replace(final_png)
                shot_files.append(final_png)
                status = "成功"
            else:
                if tmp_png.exists():
                    tmp_png.unlink()
                status = f"失敗：{res.error}"

            ws_out.append(
                [
                    item["index"],
                    item["origin"],
                    item["destination"],
                    item["vehicle"],
                    res.distance_km if res.ok else "",
                    res.route_summary,
                    res.duration_text,
                    res.candidate_count,
                    shot_name,
                    res.gmaps_url,
                    res.timestamp_utc8,
                    status,
                ]
            )

        out_xlsx_path = tmp_root / excel_filename
        wb_out.save(out_xlsx_path)

        with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(out_xlsx_path, arcname=excel_filename)
            for png in shot_files:
                zf.write(png, arcname=f"screenshots/{png.name}")

    print(f"批次處理完成！已產出：{output_zip}")
    return output_zip


def main() -> None:
    parser = argparse.ArgumentParser(description="臺灣陸地運輸最短距離與截圖 CLI 批次工具（上限 20 筆）")
    parser.add_argument("excel", type=Path, help="輸入 Excel (.xlsx) 路徑")
    parser.add_argument("-o", "--output", type=Path, default=None, help="輸出 ZIP 路徑（選填）")
    args = parser.parse_args()
    run_batch_cli(args.excel, args.output)


if __name__ == "__main__":
    main()
