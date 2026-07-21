#!/usr/bin/env python3
"""Entry point for the morf commands. See lib/morftools/cli.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from morftools.cli import main

if __name__ == "__main__":
    sys.exit(main())
