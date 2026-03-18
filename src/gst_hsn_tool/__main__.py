"""Package entrypoint for GST HSN Resolver."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _build_pythonpath(root: Path) -> str:
    existing = os.environ.get("PYTHONPATH", "")
    return str(root / "src") + (os.pathsep + existing if existing else "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GST HSN Resolver Web App")
    parser.add_argument("--azure", action="store_true", help="Run on 0.0.0.0:$PORT")
    parser.add_argument("--local", action="store_true", help="Run on localhost:8501")
    args = parser.parse_args()

    root = _project_root()
    env = os.environ.copy()
    env["PYTHONPATH"] = _build_pythonpath(root)

    port = env.get("PORT", "8000") if args.azure else "8501"
    address = "0.0.0.0" if args.azure else "localhost"

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(root / "src" / "gst_hsn_tool" / "web_app.py"),
        "--server.address",
        address,
        "--server.port",
        port,
    ]
    subprocess.run(cmd, env=env, check=False)


if __name__ == "__main__":
    main()
