#!/usr/bin/env bash
exec python3 "$(dirname "$0")/scripts/exec-bits.py" "$(cd "$(dirname "$0")/.." && pwd)" "$@"
