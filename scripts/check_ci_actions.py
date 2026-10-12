"""Reject partial CodeQL updates before running tests and security scans."""
from pathlib import Path
import re

import yaml
from yaml.nodes import MappingNode, ScalarNode, SequenceNode

USES = re.compile(r"^\s*(?:-\s*)?uses:\s*['\"]?((?i:github/codeql-action)/(?:init|autobuild|analyze|upload-sarif))@([^\s'\"]+)['\"]?\s*(?:#\s*(.*))?$")


def mapping(node):
    """Read a YAML mapping without constructing arbitrary Python objects."""
    if not isinstance(node, MappingNode):
        raise ValueError("Expected a YAML mapping")
    result = {}
    for key, value in node.value:
        if not isinstance(key, ScalarNode) or key.value in result:
            raise ValueError("Workflow mapping keys must be unique scalars")
        result[key.value] = value
    return result


def step_references(source):
    """Yield executable step references, ignoring comments and scalar text."""
    root = mapping(yaml.compose(source, Loader=yaml.BaseLoader))
    jobs = root.get("jobs")
    if jobs is None:
        return
    for job in mapping(jobs).values():
        steps = mapping(job).get("steps")
        if steps is None:
            continue
        if not isinstance(steps, SequenceNode):
            raise ValueError("Workflow steps must be a sequence")
        for step in steps.value:
            reference = mapping(step).get("uses")
            if reference is not None:
                if not isinstance(reference, ScalarNode):
                    raise ValueError("Step uses must be a scalar")
                yield step, reference


def validate(sources):
    """Require one CodeQL release in Renovate-compatible block-form steps."""
    pins = set()
    versions = set()
    for filename, source in sources.items():
        lines = source.splitlines()
        for step, reference in step_references(source):
            if not reference.value.lower().startswith("github/codeql-action/"):
                continue
            number = reference.start_mark.line + 1
            line = lines[number - 1]
            match = USES.fullmatch(line)
            if step.flow_style or match is None:
                raise ValueError(f"{filename}:{number}: Use block-form CodeQL steps with an inline release comment for Renovate")
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
