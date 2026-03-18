from __future__ import annotations

import argparse
from pathlib import Path

from gst_hsn_tool.catalog import download_and_build_master


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download official GST HSN directory and build local master CSV")
    parser.add_argument(
        "--output",
        required=True,
        help="Output CSV path for local HSN master",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output = Path(args.output)
    count = download_and_build_master(output)
    print(f"Master created: {output} ({count} rows)")


if __name__ == "__main__":
    main()
