#!/usr/bin/env python3
"""
Create a high-speed video-only manifest from the full ECN link manifest.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


VIDEO_EXTS = {".avi", ".mp4", ".gif"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in-csv", type=Path, required=True, help="Input full manifest")
    parser.add_argument("--out-csv", type=Path, required=True, help="Output filtered manifest")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.in_csv.exists():
        print(f"[error] input manifest not found: {args.in_csv}")
        return 2

    with args.in_csv.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        fieldnames = reader.fieldnames or []
        if "url" not in fieldnames:
            print("[error] input manifest missing 'url' column")
            return 2
        rows = list(reader)

    filtered = []
    for row in rows:
        ext = (row.get("extension") or "").lower()
        if ext in VIDEO_EXTS:
            filtered.append(row)

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered)

    print(f"[done] wrote {len(filtered)} high-speed links -> {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
