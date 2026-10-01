"""Extract a minimal session from HAR and read devices using littledivy/mimic.

Only the already observed list endpoint is replayed. Credentials and device
identifiers are saved privately; stdout contains telemetry and counts only.
"""
from __future__ import annotations

import json

from mimic import Session

from capture import PRIVATE, write_private

ORIGIN = "https://appadmin.desloc.com"
PATH = "/api/device/list"
HEADERS = ("authorization", "deviceid", "appversion", "systype")


def main() -> None:
    entries = json.loads((PRIVATE / "desloc.har").read_text())["log"]["entries"]
    matches = [e for e in entries if e["request"]["url"] == ORIGIN + PATH
               and e["request"]["method"] == "POST" and e["response"]["status"] == 200]
    if not matches:
        raise SystemExit("No device-list request captured")
    request = matches[-1]["request"]
    captured = {h["name"].lower(): h["value"] for h in request["headers"]}
    if any(not captured.get(key) for key in HEADERS):
        raise SystemExit("Captured request is missing a required header")
    headers = {key: captured[key] for key in HEADERS}
    body = json.loads(request["postData"]["text"])
    result = Session(ORIGIN, headers=headers).post(PATH, json=body, timeout=15,
                                                 refresh=False, allow_redirects=False)
    if not isinstance(result, dict) or result.get("status") != 200 or result.get("success") is not True:
        raise SystemExit("Device list failed; capture a new DESLOC session")
    if not isinstance(result.get("data"), list):
        raise SystemExit("Unexpected device-list response")
    write_private(PRIVATE / "ha-session.json", json.dumps({
        "token": headers["authorization"], "app_device_id": headers["deviceid"],
        "app_version": headers["appversion"], "sys_type": headers["systype"],
    }, indent=2))
    write_private(PRIVATE / "last-device-list.json", json.dumps(result, indent=2))
    print(json.dumps({"success": True, "device_commands_sent": 0, "devices": [
        {key: row.get(key) for key in ("model", "batteryValue", "networkSignal", "doorState", "onlineStatus")}
        for row in result["data"]
    ], "session_file": str(PRIVATE / "ha-session.json")}, indent=2))


if __name__ == "__main__":
    main()
