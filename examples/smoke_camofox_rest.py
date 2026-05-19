#!/usr/bin/env python3
"""Smoke-test a running jo-inc/camofox-browser REST server."""

from __future__ import annotations

import argparse
import requests


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?", default="https://example.com")
    parser.add_argument("--base-url", default="http://127.0.0.1:9377")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    health = requests.get(f"{base}/health", timeout=10)
    health.raise_for_status()
    print("health:", health.json())

    payload = {"userId": "changedetection-smoke", "sessionKey": "smoke", "url": args.url}
    tab = requests.post(f"{base}/tabs", json=payload, timeout=60)
    tab.raise_for_status()
    tab_id = tab.json()["tabId"]
    try:
        expr = "({title: document.title, length: document.documentElement.outerHTML.length})"
        result = requests.post(
            f"{base}/tabs/{tab_id}/evaluate",
            json={"userId": "changedetection-smoke", "expression": expr},
            timeout=30,
        )
        result.raise_for_status()
        print("page:", result.json()["result"])
    finally:
        requests.delete(f"{base}/tabs/{tab_id}?userId=changedetection-smoke", timeout=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
