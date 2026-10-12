"""Reject partial CodeQL updates before running tests and security scans."""
from pathlib import Path
import re

USES = re.compile(r"^\s*(?:-\s*)?uses:\s*['\"]?(github/codeql-action/(?:init|autobuild|analyze|upload-sarif))@([^\s'\"]+)['\"]?\s*(?:#\s*(.*))?$")


def validate(sources):
    pins = set()
    versions = set()
    for filename, source in sources.items():
        for number, line in enumerate(source.splitlines(), 1):
            match = USES.fullmatch(line)
            if match is None:
                continue
            _, pin, comment = match.groups()
            version = (comment or "").split()[0] if comment else ""
            if not re.fullmatch(r"[0-9a-f]{40}", pin):
                raise ValueError(f"{filename}:{number}: CodeQL needs a full commit SHA")
            if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", version):
                raise ValueError(f"{filename}:{number}: CodeQL needs a full release comment for Renovate")
            pins.add(pin)
            versions.add(version)
    if len(pins) != 1 or len(versions) != 1:
        raise ValueError("All CodeQL steps across workflows must use one SHA and release")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    validate({str(p.relative_to(root)): p.read_text() for p in (root / ".github/workflows").glob("*.y*ml")})
    print("CodeQL action SHAs and Renovate release comments are consistent.")
