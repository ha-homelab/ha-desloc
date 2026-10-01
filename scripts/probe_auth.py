"""Replay only the observed token exchange using mimic, without device commands."""
from __future__ import annotations

import base64
import json
from pathlib import Path

from mimic import Session
from mimic.extract import DROP

PRIVATE = Path(__file__).resolve().parents[1] / ".private"
URL = "https://iot.desloc.com/oauth/token"


def main() -> None:
    entries = json.loads((PRIVATE / "desloc.har").read_text())["log"]["entries"]
    candidates = [e for e in entries if e["request"]["url"] == URL
                  and e["request"]["method"] == "POST" and e["response"]["status"] == 200]
    if not candidates:
        raise SystemExit("No successful token exchange captured")
    latest = candidates[-1]
    req = latest["request"]
    if not req["postData"]["mimeType"].startswith("application/x-www-form-urlencoded"):
        raise SystemExit("Unexpected request encoding; inspect capture first")
    original = json.loads(base64.b64decode(latest["response"]["content"]["text"]))
    headers = {h["name"]: h["value"] for h in req["headers"] if h["name"].lower() not in DROP}
    session = Session("https://iot.desloc.com", headers=headers)
    # Replay the exact form body. Never retry this POST and never print tokens.
    result = session.post("/oauth/token", data=req["postData"]["text"].encode(),
                          timeout=15, refresh=False, allow_redirects=False)
    if not isinstance(result, dict):
        raise SystemExit("Unexpected response type")
    data = result.get("data") or {}
    if result.get("success") is not True or result.get("code") != "000000":
        print(json.dumps({"success": False, "code": result.get("code")}))
        raise SystemExit(1)
    print(json.dumps({
        "endpoint": URL, "success": True,
        "access_token_present": bool(data.get("accessToken")),
        "same_access_token_as_app": data.get("accessToken") == original.get("data", {}).get("accessToken"),
        "expires_in_seconds": data.get("expiresIn"),
        "device_commands_sent": 0,
    }, indent=2))


if __name__ == "__main__":
    main()
