"""本機 FastAPI 橋接服務（監聽 http://127.0.0.1:8787）。"""

from __future__ import annotations

import base64
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from engine.gmaps_shortest import (
    fetch_shortest_route_async,
    make_screenshot_filename,
)

app = FastAPI(
    title="tw-road-carbon 本機最短路徑截圖引擎",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://tw-road-carbon.pages.dev"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_private_network_access_header(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


class RouteRequest(BaseModel):
    origin: str = Field(..., min_length=1, description="起點地址")
    destination: str = Field(..., min_length=1, description="終點地址")
    vehicle: Literal["汽車", "機車"] = Field("汽車", description="Google Maps 導航車輛模式")
    index: int = Field(1, ge=1, description="項次編號（用於產出截圖檔名）")


def _get_playwright_version() -> str:
    try:
        return version("playwright")
    except PackageNotFoundError:
        return "unknown"


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "tw-road-carbon-engine",
        "playwright_version": _get_playwright_version(),
    }


@app.post("/api/route")
async def api_route(req: RouteRequest) -> dict:
    with tempfile.TemporaryDirectory(prefix="tw_road_") as tmp_dir:
        tmp_png = Path(tmp_dir) / "route.png"
        result = await fetch_shortest_route_async(
            origin=req.origin,
            destination=req.destination,
            vehicle=req.vehicle,
            output_png=tmp_png,
        )
        payload = result.to_dict()
        if result.ok and tmp_png.exists():
            raw_bytes = tmp_png.read_bytes()
            payload["screenshot_base64"] = base64.b64encode(raw_bytes).decode("ascii")
            payload["screenshot_filename"] = make_screenshot_filename(
                index=req.index,
                origin=result.origin,
                destination=result.destination,
                distance_km=result.distance_km or 0.0,
            )
        else:
            payload["screenshot_base64"] = ""
            payload["screenshot_filename"] = ""
        return payload


ROOT_DIR = Path(__file__).resolve().parent.parent
app.mount("/", StaticFiles(directory=str(ROOT_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("engine.local_server:app", host="127.0.0.1", port=8787, reload=False)
