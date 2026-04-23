"""Entry point for ``python -m simulator``."""

from __future__ import annotations

import argparse
from pathlib import Path

from simulator.runner import run_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Workload Characterization and Bottleneck Analysis benchmark",
    )
    parser.add_argument(
        "config",
        nargs="?",
        default=None,
        help="Path to config.yaml (default: config.yaml next to simulator/)",
    )
    parser.add_argument(
        "--arrival-pattern",
        choices=["poisson", "bursty", "regular"],
        default=None,
        help="Override arrival pattern from config",
    )
    parser.add_argument(
        "--read-fraction",
        type=float,
        default=None,
        help="Override read fraction (0.0–1.0) from config",
    )
    parser.add_argument(
        "--target-utilization",
        type=float,
        default=None,
        help="Override target utilisation (0.0–1.0) from config",
    )

    args = parser.parse_args()

    config_path = Path(args.config) if args.config else None
    run_benchmark(
        config_path,
        arrival_pattern=args.arrival_pattern,
        read_fraction=args.read_fraction,
        target_utilization=args.target_utilization,
    )


if __name__ == "__main__":
    main()
