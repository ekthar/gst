from __future__ import annotations

import argparse
from pathlib import Path

from gst_hsn_tool.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline GST HSN resolver")
    parser.add_argument("--input", required=True, help="Path to client Excel/CSV file")
    parser.add_argument("--hsn-master", required=True, help="Path to HSN master CSV/XLSX")
    parser.add_argument("--output", required=True, help="Path to output Excel file")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    run_pipeline(
        client_path=Path(args.input),
        hsn_master_path=Path(args.hsn_master),
        output_path=Path(args.output),
    )
    print(f"Output generated: {args.output}")


if __name__ == "__main__":
    main()
