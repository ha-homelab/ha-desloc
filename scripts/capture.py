"""Isolated, DESLOC-only capture using littledivy/mimic and mitmweb."""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import time

from mimic.sources.mitm import Mitm, hosts

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".private"
STATE = PRIVATE / "capture-state.json"


def write_private(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(path, "w", opener=lambda p, flags: os.open(p, flags, 0o600)) as f:
        f.write(data)
    path.chmod(0o600)


def state() -> dict:
    return json.loads(STATE.read_text())


def client() -> Mitm:
    info = state()
    return Mitm(info["url"], info["token"])


def start() -> None:
    if STATE.exists():
        try:
            client().flows()
        except Exception:
            pass
        else:
            status()
            return
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    PRIVATE.chmod(0o700)
    conf = PRIVATE / "mitmproxy"
    conf.mkdir(mode=0o700, exist_ok=True)
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Select the default-route address without sending a packet.
        probe.connect(("192.0.2.1", 9))
        ip = os.environ.get("DESLOC_CAPTURE_HOST") or probe.getsockname()[0]
    finally:
        probe.close()
    for bind_host, port in ((ip, 8080), ("127.0.0.1", 18081)):
        with socket.socket() as sock:
            sock.bind((bind_host, port))
    token = secrets.token_urlsafe(32)
    config = {
        "listen_host": ip,
        "listen_port": 8080,
        "web_host": "127.0.0.1",
        "web_port": 18081,
        "web_password": token,
        "web_open_browser": False,
        # Full iOS certificate trust must be enabled before app capture.
        "allow_hosts": [r"^(iot|appadmin|xsgateway)[.]desloc[.]com(:[0-9]+)?$"],
        "save_stream_file": str(PRIVATE / "desloc.mitm"),
        "save_stream_filter": '~d "^([a-z0-9-]+[.])*desloc[.]com$"',
        "termlog_verbosity": "warn",
    }
    # JSON is valid YAML, avoiding shell expansion of passwords or regexes.
    write_private(conf / "config.yaml", json.dumps(config, indent=2))
    command = [str(ROOT / ".venv/bin/mitmweb"), "--set", f"confdir={conf}"]
    with (PRIVATE / "proxy.log").open("ab") as log:
        proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
                                stderr=log, start_new_session=True)
    info = {"pid": proc.pid, "ip": ip, "url": "http://127.0.0.1:18081",
            "token": token, "started_at": datetime.now(timezone.utc).isoformat()}
    write_private(STATE, json.dumps(info, indent=2))
    for _ in range(40):
        if proc.poll() is not None:
            raise RuntimeError("Proxy exited; inspect the private proxy log")
        try:
            client().flows()
        except Exception:
            time.sleep(0.25)
        else:
            status()
            return
    raise RuntimeError("Proxy did not become ready")


def status() -> None:
    info = state()
    mitm = client()
    flows = mitm.flows()
    options_response = mitm._http.get(mitm.url + "/options", timeout=5)
    options_response.raise_for_status()
    scope = options_response.json()["allow_hosts"]["value"]
    print(json.dumps({"proxy": f"{info['ip']}:8080", "dashboard": info["url"],
                      "capture_scope": scope,
                      "flows": len(flows), "hosts": hosts(flows)}, indent=2))


def export() -> None:
    """Export app traffic locally; never print credentials or body values."""
    mitm = client()
    entries = []
    for flow in mitm.flows():
        req = flow.get("request") or {}
        host = req.get("host", "").lower()
        if host != "desloc.com" and not host.endswith(".desloc.com"):
            continue
        resp = flow.get("response") or {}
        if not resp:
            continue
        request_body = mitm.body(flow["id"], "request")
        response_body = mitm.body(flow["id"], "response")
        port = req.get("port", 443)
        authority = host if port in (80, 443) else f"{host}:{port}"
        request_headers = [{"name": k, "value": v} for k, v in req.get("headers", [])]
        response_headers = [{"name": k, "value": v} for k, v in resp.get("headers", [])]
        content_type = dict((k.lower(), v) for k, v in req.get("headers", [])).get("content-type", "")
        response_type = dict((k.lower(), v) for k, v in resp.get("headers", [])).get("content-type", "")
        entry = {
            "startedDateTime": datetime.fromtimestamp(req.get("timestamp_start", time.time()), timezone.utc).isoformat(),
            "time": 0,
            "request": {"method": req["method"],
                        "url": f"{req.get('scheme', 'https')}://{authority}{req['path']}",
                        "httpVersion": req.get("http_version", "HTTP/1.1"),
                        "headers": request_headers, "cookies": [], "queryString": [],
                        "headersSize": -1, "bodySize": len(request_body)},
            "response": {"status": resp["status_code"], "statusText": resp.get("reason", ""),
                         "httpVersion": resp.get("http_version", "HTTP/1.1"),
                         "headers": response_headers, "cookies": [], "redirectURL": "",
                         "headersSize": -1, "bodySize": len(response_body),
                         "content": {"size": len(response_body), "mimeType": response_type,
                                     "text": base64.b64encode(response_body).decode(), "encoding": "base64"}},
            "cache": {}, "timings": {"send": 0, "wait": 0, "receive": 0},
        }
        if request_body:
            # Refuse lossy conversion: replay must preserve real captured bytes.
            entry["request"]["postData"] = {"mimeType": content_type, "text": request_body.decode("utf-8")}
        entries.append(entry)
    destination = PRIVATE / "desloc.har"
    write_private(destination, json.dumps({"log": {"version": "1.2", "creator": {
        "name": "ha-desloc mimic capture", "version": "0.1"}, "entries": entries}}, indent=2))
    print(f"Exported {len(entries)} DESLOC requests to {destination}")


def run_mimic(arguments: list[str]) -> None:
    info = state()
    env = dict(os.environ, MITM_URL=info["url"], MITM_TOKEN=info["token"])
    raise SystemExit(subprocess.call([str(ROOT / ".venv/bin/mimic"), *arguments], env=env))


def stop() -> None:
    info = state()
    processes = [(info["pid"], (str(ROOT / ".venv/bin/mitmweb"), str(PRIVATE / "mitmproxy")))]
    if info.get("certificate_pid"):
        processes.append((info["certificate_pid"], (str(ROOT / "scripts/certificate_server.py"),)))
    # Check command identity before signalling PIDs loaded from disk.
    for pid, expected in processes:
        result = subprocess.run(["ps", "-p", str(pid), "-o", "command="], text=True, capture_output=True)
        if result.returncode != 0:
            continue
        if not all(part in result.stdout for part in expected):
            raise RuntimeError("PID identity changed; refusing to signal it")
        os.kill(pid, signal.SIGTERM)
    print("Proxy stopped. Set the iPhone Wi-Fi proxy to Off and remove the temporary mitmproxy profile.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["start", "status", "export", "stop", "mimic"])
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command == "mimic":
        run_mimic(args.arguments)
    else:
        globals()[args.command]()
