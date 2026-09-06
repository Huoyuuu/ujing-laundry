# /// script
# requires-python = ">=3.11"
# dependencies = ["curl-cffi", "fastapi", "uvicorn"]
# ///
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import base64
import hashlib
import hmac
import json
import time
import uuid
import os
from pathlib import Path
import re

from curl_cffi import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn

ROOT = Path(__file__).resolve().parent
app = FastAPI(docs_url=None, redoc_url=None)


def login():
    mobile = input("手机号：").strip()
    if not re.fullmatch(r"1\d{10}", mobile):
        raise ValueError("手机号格式错误")
    nonce, timestamp = uuid.uuid4().hex, int(time.time())
    key = b"T3pAWrBqKzS2GC7LKQbIDN2xkWEYzTS/nrHdYfbTkHU="
    signature = base64.b64encode(hmac.new(key, f"{nonce}{timestamp}".encode(), hashlib.sha256).digest()).decode()
    headers = {"x-app-code": "BO", "x-app-version": "1.1.0"}
    response = requests.get("https://phoenix.ujing.online/api/v1/wechat/captcha/create",
        params={"mobile": mobile, "type": 1, "nonce": nonce, "timestamp": timestamp, "signature": signature},
        headers=headers, timeout=20)
    response.raise_for_status()
    if response.json().get("code") != 0:
        raise ValueError("短信发送失败")
    captcha = input("验证码已发送，请输入验证码：").strip()
    if not re.fullmatch(r"\d{4,8}", captcha):
        raise ValueError("验证码格式错误")
    response = requests.post("https://phoenix.ujing.online/api/v1/login",
        json={"mobile": mobile, "captcha": captcha}, headers=headers, timeout=20)
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise ValueError("登录失败")
    token = payload["data"]["token"]
    if not isinstance(token, str) or not token:
        raise ValueError("登录响应缺少JWT")
    (ROOT / "ujing_config.json").write_text(json.dumps({"token": token}), encoding="utf-8")
    print("JWT：", token)
    print("已保存到", ROOT / "ujing_config.json")
    return token


@app.get("/", response_class=HTMLResponse)
def home():
    return (ROOT / "index.html").read_text(encoding="utf-8")


def query_dorm(dorm, token):
    response = requests.get(
        "https://phoenix.ujing.online/api/v1/stores/near",
        params={"lat": 41.652195, "lont": 123.427188, "scope": 2000,
                "page": 1, "size": 100, "mode": "BA", "keyword": f"{dorm}舍"},
        headers={"Authorization": f"Bearer {token}", "x-app-code": "ZA", "x-app-version": "2.4.18"},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise ValueError("API error")
    stores = payload["data"]["storeList"]
    if len(stores) >= 100:
        raise ValueError("Result exceeds demo limit")
    rooms = []
    for store in stores:
        if not re.search(fr"(?<!\d){dorm}舍", store["name"]):
            continue
        washers = [x for x in store["storeInfo"] if x["category"] == 1]
        total = sum(x["num"] for x in washers)
        idle = sum(x["access"] for x in washers)
        rooms.append({"name": store["name"].replace(f"{dorm}舍", ""), "idle": idle,
                      "total": total, "non_idle": total - idle})
    return {"dorm": dorm, "rooms": sorted(rooms, key=lambda x: x["name"]),
            "idle": sum(x["idle"] for x in rooms), "total": sum(x["total"] for x in rooms)}


@app.get("/api/status")
def status():
    try:
        token = os.environ["UJING_JWT"].removeprefix("Bearer ").strip()
        with ThreadPoolExecutor(max_workers=4) as pool:
            dorms = list(pool.map(lambda dorm: query_dorm(dorm, token), "3456"))
        result = {"updated": datetime.now().astimezone().isoformat(), "dorms": dorms}
        (ROOT / "data").mkdir(exist_ok=True)
        (ROOT / "data" / "latest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    except Exception:
        raise HTTPException(502, "查询失败，请稍后刷新；若持续失败，请重新登录。") from None


if __name__ == "__main__":
    try:
        token = os.environ.get("UJING_JWT", "").strip()
        config = ROOT / "ujing_config.json"
        if not token and config.exists():
            token = json.loads(config.read_text(encoding="utf-8")).get("token", "")
        os.environ["UJING_JWT"] = token or login()
    except (Exception, KeyboardInterrupt):
        raise SystemExit("登录取消或失败。请检查网络、手机号和验证码后重新运行；请求不会自动重试。") from None
    uvicorn.run(app, host="127.0.0.1", port=18000, access_log=False)
