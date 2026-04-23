#!/usr/bin/env bash
# Run the workload characterization and bottleneck analysis benchmark.
# Usage: bash scripts/run-benchmark.sh [path/to/config.yaml] [--arrival-pattern bursty] ...
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAB_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$LAB_DIR"

# Activate venv if present
if [ -d ".venv/bin" ]; then
    source .venv/bin/activate
elif [ -d "venv/bin" ]; then
    source venv/bin/activate
fi

python3 -m simulator "$@"
