#!/usr/bin/env python
"""
Streamlit launcher for GST HSN Resolver Web UI
Run from repo root: python run_web_app.py [streamlit args]
"""

import sys
import subprocess
from pathlib import Path
import os

if __name__ == "__main__":
    # Set up Python path
    repo_root = Path(__file__).parent
    src_path = repo_root / "src"
    
    # Add to environment
    env = os.environ.copy()
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{src_path}:{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = str(src_path)
    
    # Build streamlit command
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(repo_root / "src" / "gst_hsn_tool" / "web_app.py"),
    ]
    
    # Add any extra arguments passed to this script
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])
    
    # Run streamlit
    try:
        subprocess.run(cmd, env=env, check=False)
    except KeyboardInterrupt:
        print("\n✅ Streamlit stopped")
        sys.exit(0)

