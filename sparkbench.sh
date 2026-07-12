#!/usr/bin/env bash
set -euo pipefail
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/venv/bin/python" "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/sparkbench.py" run "$@"
