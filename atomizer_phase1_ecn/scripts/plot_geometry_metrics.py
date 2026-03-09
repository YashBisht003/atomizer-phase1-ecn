#!/usr/bin/env python3
"""Create plots from geometry metrics CSV outputs."""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame-csv", type=Path, required=True, help="Path to frame_metrics.csv")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output directory for PNG plots")
    return parser.parse_args()


def safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")


def load_rows(frame_csv: Path) -> list[dict[str, str]]:
    with frame_csv.open("r", encoding="utf-8", newline="") as fp:
        rows = list(csv.DictReader(fp))
    return rows


def to_float(value: str) -> float | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def main() -> int:
    args = parse_args()
    if not args.frame_csv.exists():
        print(f"[error] frame csv not found: {args.frame_csv}")
        return 2

    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:  # pylint: disable=broad-except
        print("[error] matplotlib not available. Install with:")
        print("        python -m pip install --user matplotlib")
        print(f"        detail: {exc}")
        return 2

    rows = load_rows(args.frame_csv)
    if not rows:
        print("[error] frame csv is empty")
        return 2

    by_video: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        if r.get("status") != "ok":
            continue
        by_video[r.get("video_id", "unknown")].append(r)
    if not by_video:
        print("[error] no rows with status=ok")
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    all_pen = []
    all_cone = []
    all_area = []

    print(f"[info] plotting videos: {len(by_video)}")
    for video_id, vrows in sorted(by_video.items()):
        parsed = []
        for r in vrows:
            t = to_float(r.get("time_ms", ""))
            p = to_float(r.get("penetration_px", ""))
            c = to_float(r.get("cone_angle_deg", ""))
            a = to_float(r.get("projected_area_px", ""))
            if t is None or p is None or a is None:
                continue
            parsed.append((t, p, c, a))
        parsed.sort(key=lambda x: x[0])
        if not parsed:
            continue

        tvals = [x[0] for x in parsed]
        pvals = [x[1] for x in parsed]
        cvals = [x[2] for x in parsed]
        avals = [x[3] for x in parsed]

        all_pen.append((video_id, tvals, pvals))
        all_cone.append((video_id, tvals, cvals))
        all_area.append((video_id, tvals, avals))

        fig, axes = plt.subplots(3, 1, figsize=(8, 10), sharex=True)
        axes[0].plot(tvals, pvals, marker="o", linewidth=1.5)
        axes[0].set_ylabel("Penetration (px)")
        axes[0].grid(alpha=0.3)

        # Drop None/NaN-like cone entries
        cone_t = [tvals[i] for i, v in enumerate(cvals) if v is not None]
        cone_v = [v for v in cvals if v is not None]
        if cone_t:
            axes[1].plot(cone_t, cone_v, marker="o", linewidth=1.5)
        axes[1].set_ylabel("Cone Angle (deg)")
        axes[1].grid(alpha=0.3)

        axes[2].plot(tvals, avals, marker="o", linewidth=1.5)
        axes[2].set_ylabel("Projected Area (px)")
        axes[2].set_xlabel("Time (ms)")
        axes[2].grid(alpha=0.3)

        fig.suptitle(video_id)
        fig.tight_layout()
        out = args.out_dir / f"{safe_name(video_id)}.png"
        fig.savefig(out, dpi=150)
        plt.close(fig)

    # Overview overlays
    def plot_overlay(series, ylabel: str, filename: str):
        fig, ax = plt.subplots(figsize=(10, 6))
        for vid, tvals, vals in series:
            if not vals:
                continue
            ax.plot(tvals, vals, linewidth=1.2, label=vid)
        ax.set_xlabel("Time (ms)")
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7, ncol=1, loc="best")
        fig.tight_layout()
        fig.savefig(args.out_dir / filename, dpi=150)
        plt.close(fig)

    plot_overlay(all_pen, "Penetration (px)", "overview_penetration.png")
    plot_overlay(all_area, "Projected Area (px)", "overview_area.png")
    # Cone rows may include None values; filter per series
    cone_series = []
    for vid, tvals, cvals in all_cone:
        tf = [tvals[i] for i, v in enumerate(cvals) if v is not None]
        vf = [v for v in cvals if v is not None]
        cone_series.append((vid, tf, vf))
    plot_overlay(cone_series, "Cone Angle (deg)", "overview_cone_angle.png")

    print(f"[done] plots written to: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
