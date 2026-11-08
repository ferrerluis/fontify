#!/usr/bin/env python3
"""Optional offline raster tracing; vector sources bypass this helper entirely."""

import argparse
import json
from pathlib import Path

from fontify.model import FontifyError
from fontify.raster import trace_sheet

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                {
                    "project": str(trace_sheet(args.plan, args.out)),
                    "status": "review_required",
                }
            )
        )
    except (FontifyError, OSError, ValueError) as e:
        parser.exit(1, f"{e}\n")
