"""Run synthetic tests against an existing HA container's Python and libraries.

Only temporary files are created. Does not install packages, access /config,
call DESLOC, restart HA, or send physical device commands.
"""
import argparse
import importlib.metadata
import io
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
REMOTE = '''import os,sys,tarfile,tempfile,subprocess
with tempfile.TemporaryDirectory(prefix="desloc-verify-") as path:
 with tarfile.open(fileobj=sys.stdin.buffer,mode="r|gz") as archive:
  archive.extractall(path,filter="data")
 env=dict(os.environ,PYTHONPATH=path+":"+path+"/.testdeps",PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
 result=subprocess.run([sys.executable,"-m","pytest","-p","pytest_asyncio.plugin","-q","--basetemp",path+"/.pytest-tmp"],cwd=path,env=env)
 sys.exit(result.returncode)
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--pod", required=True)
    args = parser.parse_args()
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w:gz") as archive:
        for folder in ("custom_components", "tests"):
            for path in (ROOT / folder).rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts:
                    archive.add(path, arcname=str(path.relative_to(ROOT)))
        archive.add(ROOT / "pytest.ini", arcname="pytest.ini")
        # pytest is already present in the target. Transfer only its pure-Python
        # asyncio plugin and distribution metadata, not the local environment.
        distribution = importlib.metadata.distribution("pytest-asyncio")
        for member in distribution.files or ():
            if "__pycache__" in member.parts or ".." in member.parts:
                continue
            path = Path(distribution.locate_file(member))
            if path.is_file():
                archive.add(path, arcname=str(Path(".testdeps") / member))
    result = subprocess.run([
        "kubectl", "--context", args.context, "-n", args.namespace,
        "exec", "-i", args.pod, "--", "python", "-c", REMOTE,
    ], input=payload.getvalue())
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
