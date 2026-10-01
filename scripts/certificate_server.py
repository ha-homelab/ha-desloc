"""Serve only this capture's public CA as an iOS profile; never serve files."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import plistlib
import uuid

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding

PRIVATE = Path(__file__).resolve().parents[1] / ".private"
CA = PRIVATE / "mitmproxy/mitmproxy-ca-cert.pem"


def profile_bytes() -> bytes:
    cert = x509.load_pem_x509_certificate(CA.read_bytes()).public_bytes(Encoding.DER)
    return plistlib.dumps({
        "PayloadType": "Configuration", "PayloadVersion": 1,
        "PayloadIdentifier": "local.desloc.capture",
        "PayloadUUID": str(uuid.uuid5(uuid.NAMESPACE_DNS, "local.desloc.capture")),
        "PayloadDisplayName": "DESLOC capture — temporary mitmproxy CA",
        "PayloadDescription": "Temporary certificate for your local DESLOC app capture. Remove after recording.",
        "PayloadContent": [{
            "PayloadType": "com.apple.security.root", "PayloadVersion": 1,
            "PayloadIdentifier": "local.desloc.capture.ca",
            "PayloadUUID": str(uuid.uuid5(uuid.NAMESPACE_DNS, "local.desloc.capture.ca")),
            "PayloadDisplayName": "mitmproxy (DESLOC capture)",
            "PayloadCertificateFileName": "mitmproxy-ca-cert.cer",
            "PayloadContent": cert,
        }],
    })


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?", 1)[0] == "/desloc.mobileconfig":
            body, content_type = profile_bytes(), "application/x-apple-aspen-config"
        elif self.path.split("?", 1)[0] == "/":
            body = b'<!doctype html><meta name="viewport" content="width=device-width"><h1>DESLOC capture</h1><p><a href="/desloc.mobileconfig">Download temporary mitmproxy certificate profile</a></p><p>Install the downloaded profile, then enable its certificate trust in iPhone Settings.</p>'
            content_type = "text/html; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if self.path.split("?", 1)[0] == "/desloc.mobileconfig":
            self.send_header("Content-Disposition", 'attachment; filename="desloc.mobileconfig"')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # No cookies, headers or query values are logged.
        pass


if __name__ == "__main__":
    info = json.loads((PRIVATE / "capture-state.json").read_text())
    ThreadingHTTPServer((info["ip"], 18080), Handler).serve_forever()
