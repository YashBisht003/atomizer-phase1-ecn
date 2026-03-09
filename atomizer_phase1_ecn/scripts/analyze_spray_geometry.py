#!/usr/bin/env python3
"""Estimate spray geometry metrics from exported frame images.

Outputs:
- frame_metrics.csv: one row per frame.
- video_summary.csv: aggregate mean/std per video folder.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from collections import defaultdict
from pathlib import Path


FRAME_RE = re.compile(r"^frame_(\d+)_t([0-9.]+)ms\.png$", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames-dir", type=Path, required=True, help="Root folder containing PNG frames")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output folder for metrics")
    parser.add_argument("--threshold", type=float, default=-1.0, help="Fixed threshold on (bg-frame); <0 => auto")
    parser.add_argument("--min-pixels", type=int, default=60, help="Minimum mask pixels to consider frame valid")
    parser.add_argument("--nozzle-frac-start", type=float, default=0.05, help="Cone-fit window start fraction")
    parser.add_argument("--nozzle-frac-end", type=float, default=0.35, help="Cone-fit window end fraction")
    parser.add_argument("--px-to-mm", type=float, default=1.0, help="Pixel to mm scale (set from calibration)")
    return parser.parse_args()


def load_gray(path: Path):
    import imageio.v2 as iio  # type: ignore
    import numpy as np  # type: ignore

    arr = iio.imread(str(path))
    if arr.ndim == 2:
        return arr.astype(np.float32)
    if arr.ndim == 3 and arr.shape[2] >= 3:
        # Luma approximation (RGB/BGR ordering differences are negligible for grayscale conversion here).
        gray = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
        return gray.astype(np.float32)
    return arr.astype(np.float32)


def group_frame_files(frames_dir: Path) -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = defaultdict(list)
    for png in frames_dir.rglob("frame_*_t*ms.png"):
        if FRAME_RE.match(png.name):
            rel_parent = str(png.parent.relative_to(frames_dir))
            groups[rel_parent].append(png)
    for key in list(groups):
        groups[key] = sorted(groups[key], key=frame_sort_key)
    return dict(sorted(groups.items()))


def frame_sort_key(path: Path) -> tuple[int, float]:
    m = FRAME_RE.match(path.name)
    if not m:
        return (10**9, 10**9)
    return (int(m.group(1)), float(m.group(2)))


def parse_frame_meta(path: Path) -> tuple[int, float]:
    m = FRAME_RE.match(path.name)
    if not m:
        return -1, float("nan")
    return int(m.group(1)), float(m.group(2))


def estimate_threshold(files: list[Path], background) -> float:
    import numpy as np  # type: ignore

    if len(files) <= 1:
        return 8.0

    sample = []
    probe_files = files[1 : min(len(files), 9)]
    for p in probe_files:
        frame = load_gray(p)
        signal = np.clip(background - frame, 0.0, None)
        sample.append(float(np.percentile(signal, 99.7)))

    if not sample:
        return 8.0
    # Conservative threshold to avoid noise while keeping spray body.
    th = max(6.0, 0.25 * float(np.median(sample)))
    return th


def compute_frame_metrics(
    mask,
    nozzle_frac_start: float,
    nozzle_frac_end: float,
):
    import numpy as np  # type: ignore

    ys, xs = np.where(mask)
    if xs.size == 0:
        return None

    # Use robust percentiles to reduce stray-noise impact.
    nozzle_x = int(np.floor(np.percentile(xs, 1.0)))
    tip_x = int(np.ceil(np.percentile(xs, 99.5)))
    penetration_px = max(0.0, float(tip_x - nozzle_x))
    area_px = int(mask.sum())

    if penetration_px <= 0:
        cone_deg = float("nan")
    else:
        x0 = int(nozzle_x + max(1, nozzle_frac_start * penetration_px))
        x1 = int(nozzle_x + max(2, nozzle_frac_end * penetration_px))
        x0 = max(0, x0)
        x1 = min(mask.shape[1] - 1, x1)
        top_pts_x = []
        top_pts_y = []
        bot_pts_x = []
        bot_pts_y = []
        for x in range(x0, x1 + 1):
            yvals = np.where(mask[:, x])[0]
            if yvals.size < 2:
                continue
            top_pts_x.append(float(x))
            top_pts_y.append(float(yvals.min()))
            bot_pts_x.append(float(x))
            bot_pts_y.append(float(yvals.max()))

        if len(top_pts_x) >= 2 and len(bot_pts_x) >= 2:
            m_top, _b_top = np.polyfit(top_pts_x, top_pts_y, 1)
            m_bot, _b_bot = np.polyfit(bot_pts_x, bot_pts_y, 1)
            cone_deg = abs(math.degrees(math.atan(m_bot) - math.atan(m_top)))
        else:
            cone_deg = float("nan")

    return {
        "nozzle_x_px": nozzle_x,
        "tip_x_px": tip_x,
        "penetration_px": penetration_px,
        "cone_angle_deg": cone_deg,
        "projected_area_px": area_px,
    }


def safe_mean(values):
    import numpy as np  # type: ignore

    arr = np.asarray([v for v in values if v == v], dtype=float)  # drop NaN
    if arr.size == 0:
        return float("nan")
    return float(arr.mean())


def safe_std(values):
    import numpy as np  # type: ignore

    arr = np.asarray([v for v in values if v == v], dtype=float)
    if arr.size <= 1:
        return float("nan")
    return float(arr.std(ddof=1))


def main() -> int:
    args = parse_args()

    if not args.frames_dir.exists():
        print(f"[error] frames dir not found: {args.frames_dir}")
        return 2
    if args.px_to_mm <= 0:
        print("[error] --px-to-mm must be > 0")
        return 2
    if not (0.0 <= args.nozzle_frac_start < args.nozzle_frac_end <= 1.0):
        print("[error] cone fit fractions must satisfy 0 <= start < end <= 1")
        return 2

    try:
        import imageio.v2 as _iio  # noqa: F401
        import numpy as _np  # noqa: F401
    except Exception as exc:  # pylint: disable=broad-except
        print("[error] missing dependencies. Install with:")
        print("        python -m pip install --user numpy imageio pillow")
        print(f"        detail: {exc}")
        return 2

    groups = group_frame_files(args.frames_dir)
    if not groups:
        print("[error] no frame images found")
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    frame_rows = []
    summary_rows = []

    print(f"[info] videos discovered: {len(groups)}")
    for idx, (video_id, files) in enumerate(groups.items(), start=1):
        background = load_gray(files[0])
        threshold = args.threshold if args.threshold >= 0 else estimate_threshold(files, background)

        ok_rows = []
        for frame_file in files:
            frame_idx, time_ms = parse_frame_meta(frame_file)
            frame = load_gray(frame_file)

            import numpy as np  # type: ignore

            signal = np.clip(background - frame, 0.0, None)
            mask = signal >= threshold
            if int(mask.sum()) < args.min_pixels:
                row = {
                    "video_id": video_id,
                    "frame_path": str(frame_file.relative_to(args.frames_dir)),
                    "frame_index": frame_idx,
                    "time_ms": time_ms,
                    "threshold": threshold,
                    "status": "too_small",
                    "nozzle_x_px": "",
                    "tip_x_px": "",
                    "penetration_px": "",
                    "penetration_mm": "",
                    "cone_angle_deg": "",
                    "projected_area_px": int(mask.sum()),
                    "projected_area_mm2": "",
                }
                frame_rows.append(row)
                continue

            geom = compute_frame_metrics(mask, args.nozzle_frac_start, args.nozzle_frac_end)
            if geom is None:
                row = {
                    "video_id": video_id,
                    "frame_path": str(frame_file.relative_to(args.frames_dir)),
                    "frame_index": frame_idx,
                    "time_ms": time_ms,
                    "threshold": threshold,
                    "status": "no_mask",
                    "nozzle_x_px": "",
                    "tip_x_px": "",
                    "penetration_px": "",
                    "penetration_mm": "",
                    "cone_angle_deg": "",
                    "projected_area_px": 0,
                    "projected_area_mm2": "",
                }
                frame_rows.append(row)
                continue

            penetration_mm = geom["penetration_px"] * args.px_to_mm
            area_mm2 = geom["projected_area_px"] * (args.px_to_mm ** 2)
            row = {
                "video_id": video_id,
                "frame_path": str(frame_file.relative_to(args.frames_dir)),
                "frame_index": frame_idx,
                "time_ms": time_ms,
                "threshold": threshold,
                "status": "ok",
                "nozzle_x_px": geom["nozzle_x_px"],
                "tip_x_px": geom["tip_x_px"],
                "penetration_px": f"{geom['penetration_px']:.6f}",
                "penetration_mm": f"{penetration_mm:.6f}",
                "cone_angle_deg": f"{geom['cone_angle_deg']:.6f}" if geom["cone_angle_deg"] == geom["cone_angle_deg"] else "",
                "projected_area_px": geom["projected_area_px"],
                "projected_area_mm2": f"{area_mm2:.6f}",
            }
            frame_rows.append(row)
            ok_rows.append(row)

        pen_vals = [float(r["penetration_px"]) for r in ok_rows if r["penetration_px"] != ""]
        cone_vals = [float(r["cone_angle_deg"]) for r in ok_rows if r["cone_angle_deg"] != ""]
        area_vals = [float(r["projected_area_px"]) for r in ok_rows if r["projected_area_px"] != ""]

        summary_rows.append(
            {
                "video_id": video_id,
                "n_frames": len(files),
                "n_ok": len(ok_rows),
                "threshold": f"{threshold:.6f}",
                "penetration_px_mean": f"{safe_mean(pen_vals):.6f}",
                "penetration_px_std": f"{safe_std(pen_vals):.6f}",
                "cone_angle_deg_mean": f"{safe_mean(cone_vals):.6f}",
                "cone_angle_deg_std": f"{safe_std(cone_vals):.6f}",
                "projected_area_px_mean": f"{safe_mean(area_vals):.6f}",
                "projected_area_px_std": f"{safe_std(area_vals):.6f}",
            }
        )

        print(f"[{idx}/{len(groups)}] video={video_id} ok={len(ok_rows)}/{len(files)} threshold={threshold:.3f}")

    frame_csv = args.out_dir / "frame_metrics.csv"
    summary_csv = args.out_dir / "video_summary.csv"

    with frame_csv.open("w", encoding="utf-8", newline="") as fp:
        fields = [
            "video_id",
            "frame_path",
            "frame_index",
            "time_ms",
            "threshold",
            "status",
            "nozzle_x_px",
            "tip_x_px",
            "penetration_px",
            "penetration_mm",
            "cone_angle_deg",
            "projected_area_px",
            "projected_area_mm2",
        ]
        writer = csv.DictWriter(fp, fieldnames=fields)
        writer.writeheader()
        writer.writerows(frame_rows)

    with summary_csv.open("w", encoding="utf-8", newline="") as fp:
        fields = [
            "video_id",
            "n_frames",
            "n_ok",
            "threshold",
            "penetration_px_mean",
            "penetration_px_std",
            "cone_angle_deg_mean",
            "cone_angle_deg_std",
            "projected_area_px_mean",
            "projected_area_px_std",
        ]
        writer = csv.DictWriter(fp, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary_rows)

    n_ok_total = sum(1 for r in frame_rows if r["status"] == "ok")
    print(f"[done] frame metrics: {frame_csv}")
    print(f"[done] video summary: {summary_csv}")
    print(f"[done] ok frames: {n_ok_total}/{len(frame_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
