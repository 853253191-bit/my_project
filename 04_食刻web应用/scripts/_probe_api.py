# -*- coding: utf-8 -*-
import json
import urllib.request

BASE = "http://118.178.131.84"


def post(path: str, payload: dict, timeout: int = 120) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print(path, resp.status, body[:800])
    except Exception as exc:  # noqa: BLE001
        print(path, "ERROR", exc)


def main() -> None:
    with urllib.request.urlopen(BASE + "/api/health", timeout=20) as resp:
        print("/api/health", resp.read().decode())
    post("/api/parse_intent", {"text": "今天好累想喝热汤"}, timeout=90)
    post("/api/recommend", {"query_text": "热汤", "filters": {}, "top_k": 1}, timeout=180)


if __name__ == "__main__":
    main()
