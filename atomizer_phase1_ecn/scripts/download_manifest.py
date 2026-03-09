#!/usr/bin/env python3
"""
Download files listed in a CSV manifest.
"""

from __future__ import annotations

import argparse
import csv
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="CSV with a url column")
    parser.add_argument("--out-dir", type=Path, required=True, help="Download root directory")
    parser.add_argument("--workers", type=int, default=6, help="Parallel downloads")
    parser.add_argument("--max-files", type=int, default=0, help="Limit files for smoke test")
    parser.add_argument(
        "--allow-ext",
        type=str,
        default="",
        help="Comma-separated extension filter (example: .txt,.csv,.avi)",
    )
    parser.add_argument(
        "--contains",
        type=str,
        default="",
        help="Only download URLs that contain this case-insensitive substring",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    parser.add_argument("--timeout", type=int, default=90, help="HTTP timeout in seconds")
    parser.add_argument("--retries", type=int, default=3, help="Retries per file")
    return parser.parse_args()


def read_manifest(manifest: Path) -> list[str]:
    with manifest.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        if "url" not in (reader.fieldnames or []):
            raise ValueError("Manifest must include a 'url' column")
        urls = [row["url"].strip() for row in reader if row.get("url", "").strip()]
    return urls


def target_path(url: str, out_dir: Path) -> Path:
    parsed = urlparse(url)
    host = parsed.netloc.replace(":", "_")
    rel_path = unquote(parsed.path.lstrip("/"))
    if not rel_path or rel_path.endswith("/"):
        rel_path = f"{rel_path}index.html"
    return out_dir / host / rel_path


def filter_urls(urls: list[str], allow_ext: str, contains: str) -> list[str]:
    filtered = urls
    if allow_ext.strip():
        ext_set = {e.strip().lower() for e in allow_ext.split(",") if e.strip()}
        filtered = [u for u in filtered if Path(urlparse(u).path).suffix.lower() in ext_set]
    if contains.strip():
        needle = contains.strip().lower()
        filtered = [u for u in filtered if needle in u.lower()]
    return filtered


def download_one(
    url: str,
    out_dir: Path,
    overwrite: bool,
    timeout: int,
    retries: int,
    lock: threading.Lock,
) -> dict[str, Any]:
    dst = target_path(url, out_dir)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")

    if dst.exists() and not overwrite:
        return {"url": url, "path": str(dst), "status": "skipped", "bytes": dst.stat().st_size}

    last_error = ""
    for attempt in range(1, retries + 1):
        try:
            req = Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Phase1-ECN-Downloader)",
                    "Accept": "*/*",
                },
            )
            with urlopen(req, timeout=timeout) as resp, tmp.open("wb") as out:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    out.write(chunk)
            os.replace(tmp, dst)
            return {
                "url": url,
                "path": str(dst),
                "status": "downloaded",
                "bytes": dst.stat().st_size,
            }
        except Exception as exc:  # pylint: disable=broad-except
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(min(2 * attempt, 6))
            with lock:
                if tmp.exists():
                    tmp.unlink(missing_ok=True)
    return {"url": url, "path": str(dst), "status": "failed", "bytes": 0, "error": last_error}


def main() -> int:
    args = parse_args()
    if not args.manifest.exists():
        print(f"[error] manifest not found: {args.manifest}")
        return 2

    urls = read_manifest(args.manifest)
    urls = filter_urls(urls, args.allow_ext, args.contains)
    if args.max_files > 0:
        urls = urls[: args.max_files]
    if not urls:
        print("[error] no URLs to download")
        return 2

    print(f"[info] queued files: {len(urls)}")
    print(f"[info] output dir: {args.out_dir}")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    lock = threading.Lock()
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [
            pool.submit(
                download_one,
                url,
                args.out_dir,
                args.overwrite,
                args.timeout,
                args.retries,
                lock,
            )
            for url in urls
        ]
        for idx, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            results.append(result)
            print(f"[{idx}/{len(urls)}] {result['status']}: {result['url']}")

    downloaded = [r for r in results if r["status"] == "downloaded"]
    skipped = [r for r in results if r["status"] == "skipped"]
    failed = [r for r in results if r["status"] == "failed"]
    total_bytes = sum(r.get("bytes", 0) for r in downloaded)

    print(
        f"[done] downloaded={len(downloaded)} skipped={len(skipped)} "
        f"failed={len(failed)} bytes={total_bytes}"
    )

    failures_csv = args.out_dir / "download_failures.csv"
    if failed:
        with failures_csv.open("w", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=["url", "path", "status", "error"])
            writer.writeheader()
            for row in failed:
                writer.writerow(
                    {
                        "url": row["url"],
                        "path": row.get("path", ""),
                        "status": row["status"],
                        "error": row.get("error", ""),
                    }
                )
        print(f"[warn] failures logged: {failures_csv}")

    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
