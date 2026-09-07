from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
from pathlib import Path
import re
import time

from curl_cffi import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn

ROOT = Path(__file__).resolve().parent
app = FastAPI(docs_url=None, redoc_url=None)
WAIT_CACHE = {}


@app.get("/", response_class=HTMLResponse)
def home():
    return (ROOT / "index.html").read_text(encoding="utf-8")


def query_device_waits(store_id, token):
    cached = WAIT_CACHE.get(store_id)
    if cached and time.monotonic() - cached["at"] < 60:
        return cached["value"]
    response = requests.get(
        "https://phoenix.ujing.online/api/v1/devices/reserve",
        params={"storeId": store_id},
        headers={"Authorization": f"Bearer {token}",
                 "x-app-code": "ZA", "x-app-version": "2.4.18"},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise ValueError("Device API error")
    result = []
    for item in payload.get("data", {}).get("devices", []):
        device = item.get("device", {})
        name = device.get("deviceTypeName", "洗衣机")
        if "烘干" in name or "干衣" in name:
            continue
        result.append({
            "name": name,
            "idle": device.get("free", 0),
            "total": device.get("total", 0),
            "wait_minutes": device.get("waitTime", 0),
        })
    WAIT_CACHE[store_id] = {"at": time.monotonic(), "value": result}
    return result


def query_dorm(dorm, token):
    response = requests.get(
        "https://phoenix.ujing.online/api/v1/stores/near",
        params={"lat": 41.652195, "lont": 123.427188, "scope": 2000,
                "page": 1, "size": 100, "mode": "BA", "keyword": f"{dorm}舍"},
        headers={"Authorization": f"Bearer {token}",
                 "x-app-code": "ZA", "x-app-version": "2.4.18"},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise ValueError("API error")
    stores = payload["data"]["storeList"]
    if len(stores) >= 100:
        raise ValueError("Result exceeds demo limit")

    def room_result(store):
        if not re.search(fr"(?<!\d){dorm}舍", store["name"]):
            return None
        washers = [x for x in store["storeInfo"] if x["category"] == 1]
        total = sum(x["num"] for x in washers)
        idle = sum(x["access"] for x in washers)
        machines = []
        if total > idle:
            try:
                machines = query_device_waits(store["id"], token)
            except Exception:
                pass
        return {"name": store["name"].replace(f"{dorm}舍", ""), "idle": idle,
                "total": total, "non_idle": total - idle, "machines": machines}
    with ThreadPoolExecutor(max_workers=8) as pool:
        rooms = [room for room in pool.map(room_result, stores) if room]
    return {"dorm": dorm, "rooms": sorted(rooms, key=lambda x: x["name"]),
            "idle": sum(x["idle"] for x in rooms), "total": sum(x["total"] for x in rooms)}


@app.get("/api/status")
def status():
    try:
        token = os.environ.get("UJING_JWT", "").removeprefix("Bearer ").strip()
        if not token:
            cfg = ROOT / "ujing_config.json"
            token = json.loads(cfg.read_text(encoding="utf-8")).get("token", "") if cfg.exists() else ""
        with ThreadPoolExecutor(max_workers=4) as pool:
            dorms = list(
                pool.map(lambda dorm: query_dorm(dorm, token), "3456"))
        result = {"updated": datetime.now().astimezone().isoformat(),
                  "dorms": dorms}
        (ROOT / "data").mkdir(exist_ok=True)
        (ROOT / "data" / "latest.json").write_text(json.dumps(result,
                                                              ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    except Exception:
        raise HTTPException(502, "查询失败，请稍后刷新；若持续失败，请重新登录。") from None


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=19000, access_log=False)
