#!/usr/bin/env python3
"""
Extract direct downloadable dataset links from ECN seed pages.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen


HREF_RE = re.compile(r"""href\s*=\s*['"]([^'"]+)['"]""", re.IGNORECASE)

DATA_EXTENSIONS = {
    ".avi",
    ".mp4",
    ".mov",
    ".m4v",
    ".mkv",
    ".gif",
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".gz",
    ".csv",
    ".txt",
    ".tsv",
    ".xls",
    ".xlsx",
    ".mat",
    ".h5",
    ".hdf5",
    ".nc",
    ".json",
    ".xml",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".bmp",
    ".dat",
}


def read_seed_urls(seed_file: Path) -> list[str]:
    lines = seed_file.read_text(encoding="utf-8").splitlines()
    urls = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        urls.append(s)
    return urls


def fetch_html(url: str, timeout: int = 30) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Phase1-ECN-LinkExtractor)",
            "Accept": "text/html,*/*",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return raw.decode("utf-8", errors="ignore")


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    # Drop fragments for stable dedupe
    parsed = parsed._replace(fragment="")
    return urlunparse(parsed)


def is_data_link(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.path.lower().startswith(("javascript:", "mailto:")):
        return False

    path_lower = parsed.path.lower()
    if any(path_lower.endswith(ext) for ext in DATA_EXTENSIONS):
        return True
    if "/sites/default/files/" in path_lower:
        return True
    if "download" in parsed.query.lower():
        return True
    return False


def extract_hrefs(page_url: str, html: str) -> Iterable[str]:
    for match in HREF_RE.finditer(html):
        href = match.group(1).strip()
        if not href:
            continue
        if href.startswith(("#", "mailto:", "javascript:")):
            continue
        yield normalize_url(urljoin(page_url, href))


def build_manifest(seed_urls: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for seed in seed_urls:
        print(f"[extract] scanning: {seed}")
        try:
            html = fetch_html(seed)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"[warn] failed to fetch seed page: {seed} ({exc})")
            continue

        for candidate in extract_hrefs(seed, html):
            if not is_data_link(candidate):
                continue
            if candidate in seen:
                continue
            seen.add(candidate)

            parsed = urlparse(candidate)
            filename = Path(parsed.path).name or "downloaded_file"
            ext = Path(filename).suffix.lower()
            rows.append(
                {
                    "source_page": seed,
                    "url": candidate,
                    "host": parsed.netloc,
                    "filename": filename,
                    "extension": ext,
                }
            )
    return sorted(rows, key=lambda r: r["url"])


def write_manifest(rows: list[dict[str, str]], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["source_page", "url", "host", "filename", "extension"]
    with out_csv.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-file", type=Path, required=True, help="Path to seed URL list")
    parser.add_argument("--out-csv", type=Path, required=True, help="Output CSV manifest")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.seed_file.exists():
        print(f"[error] seed file not found: {args.seed_file}")
        return 2
    seed_urls = read_seed_urls(args.seed_file)
    if not seed_urls:
        print("[error] no seed URLs found")
        return 2
    rows = build_manifest(seed_urls)
    write_manifest(rows, args.out_csv)
    print(f"[done] wrote {len(rows)} links -> {args.out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
