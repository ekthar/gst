from __future__ import annotations

import argparse
from pathlib import Path

from gst_hsn_tool.config import TRAINING_CORPUS_FILE
from gst_hsn_tool.training import run_training_mode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run AI training mode repeatedly until target corpus size")
    parser.add_argument("--target-gb", type=float, default=1.0, help="Target corpus size in GB")
    parser.add_argument("--max-runs", type=int, default=50, help="Maximum training iterations")
    parser.add_argument("--master", default="data/hsn_master_from_gst.csv", help="Path to current master CSV")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    target_mb = args.target_gb * 1024
    master = Path(args.master)

    print(f"Starting bulk training: target={args.target_gb} GB, max_runs={args.max_runs}")
    for i in range(1, args.max_runs + 1):
        summary = run_training_mode(master)
        size_mb = float(summary.get("corpus_size_mb", 0))
        rows = int(summary.get("corpus_rows", 0))
        print(
            f"Run {i}: pages={summary.get('web_pages_visited', 0)}, "
            f"pairs={summary.get('web_pairs_collected', 0)}, corpus_rows={rows}, corpus_mb={size_mb}"
        )

        if size_mb >= target_mb:
            print("Target reached.")
            print(f"Corpus: {summary.get('corpus_file', TRAINING_CORPUS_FILE)}")
            return

    print("Target not reached within max runs.")
    print(f"Current corpus: {Path(TRAINING_CORPUS_FILE)}")


if __name__ == "__main__":
    main()
