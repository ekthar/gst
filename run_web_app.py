#!/usr/bin/env python
"""Streamlit launcher for GST HSN Resolver Web UI.

Supports both normal Python execution and PyInstaller-frozen executable mode.
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path


def _base_dir() -> Path:
    # In frozen mode, PyInstaller extracts bundled files under _MEIPASS.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def _resolve_app_script() -> Path:
    base = _base_dir()
    candidate = base / "src" / "gst_hsn_tool" / "web_app.py"
    if candidate.exists():
        return candidate

    # Fallback for source-tree execution.
    fallback = Path(__file__).resolve().parent / "src" / "gst_hsn_tool" / "web_app.py"
    return fallback


def _prepare_args(raw_args: list[str]) -> list[str]:
    def _is_port_available(port: int, host: str = "127.0.0.1") -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                return True
            except OSError:
                return False

    def _find_open_port(start_port: int, host: str = "127.0.0.1", max_tries: int = 25) -> int:
        for offset in range(max_tries):
            candidate = start_port + offset
            if _is_port_available(candidate, host):
                return candidate
        return start_port

    args = list(raw_args)
    if "--local" in args:
        args = [a for a in args if a != "--local"]
        preferred_port = 8501
        selected_port = _find_open_port(preferred_port, "127.0.0.1")
        if selected_port != preferred_port:
            print(f"Port {preferred_port} is busy. Using port {selected_port} instead.")
        args.extend(["--server.address", "127.0.0.1", "--server.port", str(selected_port)])
    elif "--azure" in args:
        args = [a for a in args if a != "--azure"]
        args.extend(["--server.address", "0.0.0.0", "--server.port", os.environ.get("PORT", "8501")])
    elif not args:
        preferred_port = 8501
        selected_port = _find_open_port(preferred_port, "127.0.0.1")
        if selected_port != preferred_port:
            print(f"Port {preferred_port} is busy. Using port {selected_port} instead.")
        args = ["--server.address", "127.0.0.1", "--server.port", str(selected_port)]
    return args


def main() -> int:
    # Packaged EXE should always run in production mode.
    if getattr(sys, "frozen", False):
        os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"

    app_script = _resolve_app_script()
    if not app_script.exists():
        print(f"App script not found: {app_script}")
        return 1

    # Ensure imports like gst_hsn_tool.* work in source mode.
    src_path = str(app_script.parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    streamlit_args = _prepare_args(sys.argv[1:])

    from streamlit.web import cli as stcli

    # Streamlit CLI reads configuration from sys.argv.
    sys.argv = ["streamlit", "run", str(app_script), *streamlit_args]
    return int(stcli.main() or 0)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nStreamlit stopped")
        raise SystemExit(0)

