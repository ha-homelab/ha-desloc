"""Print endpoint structure without auth headers, body values, or query values."""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


def shape(value):
    if isinstance(value, dict):
        return {key: shape(item) for key, item in value.items()}
    if isinstance(value, list):
        # Show structure only, including heterogeneous array entries.
        return list({json.dumps(shape(item), sort_keys=True): shape(item)
                     for item in value[:5]}.values())
    return type(value).__name__


def body_shape(content, *, form=False):
    if not content:
        return None
    text = content.get("text", "")
    if content.get("encoding") == "base64":
        text = base64.b64decode(text).decode("utf-8", errors="replace")
    try:
        return shape(json.loads(text))
    except (ValueError, TypeError):
        if form and "application/x-www-form-urlencoded" in content.get("mimeType", ""):
            return {key: "str" for key in parse_qs(text, keep_blank_values=True)}
        return {"mime_type": content.get("mimeType"), "length": len(text)}


def inspect(path: Path):
    entries = json.loads(path.read_text())["log"]["entries"]
    result = []
    for entry in entries:
        req, resp = entry["request"], entry["response"]
        url = urlsplit(req["url"])
        # Paths can include opaque identifiers: this report stays local too.
        result.append({
            "time": entry.get("startedDateTime"), "host": url.hostname,
            "method": req["method"], "path": url.path,
            "query_keys": sorted(parse_qs(url.query, keep_blank_values=True)),
            "request_header_names": sorted(h["name"] for h in req.get("headers", [])),
            "request_shape": body_shape(req.get("postData"), form=True),
            "status": resp["status"],
            "response_shape": body_shape(resp.get("content")),
        })
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("har", nargs="?", type=Path,
                   default=Path(__file__).resolve().parents[1] / ".private/desloc.har")
    print(json.dumps(inspect(p.parse_args().har), indent=2))
