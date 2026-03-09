#!/usr/bin/env python3
"""Compare extracted geometry metrics with ECN Spray G reference curves.

Outputs:
- comparison_rows.csv: one row per (video, metric, reference variant).
- best_rows.csv: best RMSE row per (video, metric).
- overlay plots in output directory.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame-csv", type=Path, required=True, help="Path to frame_metrics.csv")
    parser.add_argument(
        "--reference-dir",
        type=Path,
        required=True,
        help="Directory containing Spray_G*_avg_* reference .txt files",
    )
    parser.add_argument("--out-dir", type=Path, required=True, help="Output folder")
    parser.add_argument("--min-points", type=int, default=6, help="Minimum points for comparison")
    parser.add_argument(
        "--include-regex",
        type=str,
        default=".*",
        help="Only compare video_id values matching this regex (example: '__avi$')",
    )
    return parser.parse_args()


def safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")


def extract_group(video_id: str) -> str | None:
    m = re.search(r"spray_g([123])", video_id, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def read_frame_rows(frame_csv: Path) -> list[dict[str, str]]:
    with frame_csv.open("r", encoding="utf-8", newline="") as fp:
        return list(csv.DictReader(fp))


def read_reference_txt(path: Path) -> tuple[list[float], list[float], list[float]]:
    tvals: list[float] = []
    means: list[float] = []
    stds: list[float] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s:
            continue
        parts = s.split()
        if len(parts) < 2:
            continue
        try:
            t = float(parts[0])
            m = float(parts[1])
            sd = float(parts[2]) if len(parts) >= 3 else float("nan")
        except ValueError:
            continue
        tvals.append(t)
        means.append(m)
        stds.append(sd)
    return tvals, means, stds


def normalize_time(tvals: list[float]) -> list[float]:
    if not tvals:
        return []
    t0 = min(tvals)
    t1 = max(tvals)
    if t1 <= t0:
        return [0.0 for _ in tvals]
    return [(t - t0) / (t1 - t0) for t in tvals]


def interpolate(ref_t: list[float], ref_y: list[float], query_t: list[float]) -> list[float]:
    import numpy as np  # type: ignore

    if len(ref_t) < 2:
        return [float("nan")] * len(query_t)
    x = np.asarray(ref_t, dtype=float)
    y = np.asarray(ref_y, dtype=float)
    q = np.asarray(query_t, dtype=float)
    return np.interp(q, x, y).tolist()


def metrics(pred: list[float], ref: list[float]) -> dict[str, float]:
    import numpy as np  # type: ignore

    p = np.asarray(pred, dtype=float)
    r = np.asarray(ref, dtype=float)
    err = p - r
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))
    bias = float(np.mean(err))
    return {"mae": mae, "rmse": rmse, "bias": bias}


def scale_least_squares(x: list[float], y: list[float]) -> float:
    import numpy as np  # type: ignore

    xv = np.asarray(x, dtype=float)
    yv = np.asarray(y, dtype=float)
    denom = float(np.dot(xv, xv))
    if abs(denom) < 1e-12:
        return float("nan")
    return float(np.dot(xv, yv) / denom)


def build_reference_map(reference_dir: Path) -> dict[str, Path]:
    refs: dict[str, Path] = {}
    for p in reference_dir.glob("Spray_G*_avg_*.txt"):
        refs[p.name] = p
    return refs


def select_ref_series(t: list[float], y: list[float]) -> tuple[list[float], list[float]]:
    # Focus on active spray window where reference mean > 0.
    idx = [i for i, v in enumerate(y) if v > 0]
    if len(idx) < 2:
        return t, y
    i0, i1 = min(idx), max(idx)
    return t[i0 : i1 + 1], y[i0 : i1 + 1]


def ensure_matplotlib():
    try:
        import matplotlib.pyplot as plt  # type: ignore # noqa: F401
    except Exception:
        return False
    return True


def plot_overlay(
    out_path: Path,
    title: str,
    x_label: str,
    y_label: str,
    t_model: list[float],
    y_model: list[float],
    t_ref: list[float],
    y_ref: list[float],
):
    import matplotlib.pyplot as plt  # type: ignore

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(t_model, y_model, marker="o", linewidth=1.5, label="our_curve")
    ax.plot(t_ref, y_ref, linewidth=1.8, label="reference_interp")
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main() -> int:
    args = parse_args()
    if not args.frame_csv.exists():
        print(f"[error] frame csv not found: {args.frame_csv}")
        return 2
    if not args.reference_dir.exists():
        print(f"[error] reference dir not found: {args.reference_dir}")
        return 2

    rows = read_frame_rows(args.frame_csv)
    rows = [r for r in rows if r.get("status") == "ok"]
    if not rows:
        print("[error] no status=ok rows in frame csv")
        return 2

    by_video: dict[str, list[dict[str, str]]] = defaultdict(list)
    include_re = re.compile(args.include_regex)
    for r in rows:
        vid = r.get("video_id", "unknown")
        if not include_re.search(vid):
            continue
        by_video[vid].append(r)

    refs = build_reference_map(args.reference_dir)
    if not refs:
        print("[error] no Spray_G*_avg_*.txt files found in reference dir")
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = args.out_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    compare_rows: list[dict[str, str]] = []
    have_mpl = ensure_matplotlib()

    pen_variants = ["LVF%3D0.2", "LVF%3D2", "vapor"]
    cone_variant = "vapor"

    print(f"[info] videos in frame csv: {len(by_video)}")
    for video_id, vrows in sorted(by_video.items()):
        group = extract_group(video_id)
        if group is None:
            continue

        parsed = []
        for r in vrows:
            try:
                t = float(r["time_ms"])
                p = float(r["penetration_px"]) if r.get("penetration_px", "") else float("nan")
                c = float(r["cone_angle_deg"]) if r.get("cone_angle_deg", "") else float("nan")
            except ValueError:
                continue
            parsed.append((t, p, c))
        parsed.sort(key=lambda x: x[0])
        if len(parsed) < args.min_points:
            continue

        t_model_raw = [x[0] for x in parsed]
        pen_model = [x[1] for x in parsed]
        cone_model = [x[2] for x in parsed]
        t_model = normalize_time(t_model_raw)

        # Penetration comparisons (scaled px->mm for fair curve-shape comparison).
        for variant in pen_variants:
            fname = f"Spray_G{group}_avg_AXIALPENvsTIME_{variant}.txt"
            ref_path = refs.get(fname)
            if not ref_path:
                continue
            t_ref, y_ref, _ = read_reference_txt(ref_path)
            t_ref, y_ref = select_ref_series(t_ref, y_ref)
            if len(t_ref) < 2:
                continue
            t_ref_n = normalize_time(t_ref)
            ref_interp = interpolate(t_ref_n, y_ref, t_model)
            if len(ref_interp) < args.min_points:
                continue

            alpha = scale_least_squares(pen_model, ref_interp)
            pen_scaled = [alpha * v for v in pen_model]
            stats = metrics(pen_scaled, ref_interp)
            compare_rows.append(
                {
                    "video_id": video_id,
                    "spray_group": f"G{group}",
                    "metric": "penetration",
                    "reference_variant": variant,
                    "n_points": str(len(ref_interp)),
                    "scale_factor_mm_per_px": f"{alpha:.8f}",
                    "mae": f"{stats['mae']:.8f}",
                    "rmse": f"{stats['rmse']:.8f}",
                    "bias": f"{stats['bias']:.8f}",
                    "our_mean": f"{sum(pen_scaled)/len(pen_scaled):.8f}",
                    "ref_mean": f"{sum(ref_interp)/len(ref_interp):.8f}",
                }
            )

            if have_mpl:
                out = plot_dir / f"{safe_name(video_id)}__penetration__{safe_name(variant)}.png"
                plot_overlay(
                    out,
                    f"{video_id} penetration vs {variant}",
                    "Normalized Time",
                    "Penetration (mm, scaled)",
                    t_model,
                    pen_scaled,
                    t_model,
                    ref_interp,
                )

        # Cone-angle comparison (direct deg->deg)
        cone_pairs = [(t, c) for t, c in zip(t_model, cone_model) if c == c]
        if len(cone_pairs) >= args.min_points:
            fname = f"Spray_G{group}_avg_CONEANGLEvsTIME_{cone_variant}.txt"
            ref_path = refs.get(fname)
            if ref_path:
                t_ref, y_ref, _ = read_reference_txt(ref_path)
                t_ref, y_ref = select_ref_series(t_ref, y_ref)
                if len(t_ref) >= 2:
                    t_ref_n = normalize_time(t_ref)
                    t_cone = [t for t, _ in cone_pairs]
                    cone_vals = [c for _, c in cone_pairs]
                    ref_interp = interpolate(t_ref_n, y_ref, t_cone)
                    stats = metrics(cone_vals, ref_interp)
                    compare_rows.append(
                        {
                            "video_id": video_id,
                            "spray_group": f"G{group}",
                            "metric": "cone_angle",
                            "reference_variant": cone_variant,
                            "n_points": str(len(ref_interp)),
                            "scale_factor_mm_per_px": "",
                            "mae": f"{stats['mae']:.8f}",
                            "rmse": f"{stats['rmse']:.8f}",
                            "bias": f"{stats['bias']:.8f}",
                            "our_mean": f"{sum(cone_vals)/len(cone_vals):.8f}",
                            "ref_mean": f"{sum(ref_interp)/len(ref_interp):.8f}",
                        }
                    )
                    if have_mpl:
                        out = plot_dir / f"{safe_name(video_id)}__cone_angle__vapor.png"
                        plot_overlay(
                            out,
                            f"{video_id} cone-angle vs vapor",
                            "Normalized Time",
                            "Cone Angle (deg)",
                            t_cone,
                            cone_vals,
                            t_cone,
                            ref_interp,
                        )

        print(f"[ok] compared video: {video_id}")

    if not compare_rows:
        print("[error] no comparison rows produced")
        return 2

    compare_csv = args.out_dir / "comparison_rows.csv"
    with compare_csv.open("w", encoding="utf-8", newline="") as fp:
        fields = [
            "video_id",
            "spray_group",
            "metric",
            "reference_variant",
            "n_points",
            "scale_factor_mm_per_px",
            "mae",
            "rmse",
            "bias",
            "our_mean",
            "ref_mean",
        ]
        writer = csv.DictWriter(fp, fieldnames=fields)
        writer.writeheader()
        writer.writerows(compare_rows)

    # Best row per (video, metric) by minimum RMSE
    best_map: dict[tuple[str, str], dict[str, str]] = {}
    for r in compare_rows:
        key = (r["video_id"], r["metric"])
        cur = best_map.get(key)
        if cur is None or float(r["rmse"]) < float(cur["rmse"]):
            best_map[key] = r
    best_rows = sorted(best_map.values(), key=lambda r: (r["video_id"], r["metric"]))

    best_csv = args.out_dir / "best_rows.csv"
    with best_csv.open("w", encoding="utf-8", newline="") as fp:
        fields = [
            "video_id",
            "spray_group",
            "metric",
            "reference_variant",
            "n_points",
            "scale_factor_mm_per_px",
            "mae",
            "rmse",
            "bias",
            "our_mean",
            "ref_mean",
        ]
        writer = csv.DictWriter(fp, fieldnames=fields)
        writer.writeheader()
        writer.writerows(best_rows)

    # Aggregate summary by metric
    summary_csv = args.out_dir / "aggregate_summary.csv"
    by_metric: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in best_rows:
        by_metric[r["metric"]].append(r)
    with summary_csv.open("w", encoding="utf-8", newline="") as fp:
        fields = ["metric", "rows", "mae_mean", "rmse_mean", "bias_mean"]
        writer = csv.DictWriter(fp, fieldnames=fields)
        writer.writeheader()
        for metric_name, items in sorted(by_metric.items()):
            mae_vals = [float(x["mae"]) for x in items]
            rmse_vals = [float(x["rmse"]) for x in items]
            bias_vals = [float(x["bias"]) for x in items]
            writer.writerow(
                {
                    "metric": metric_name,
                    "rows": len(items),
                    "mae_mean": f"{sum(mae_vals)/len(mae_vals):.8f}",
                    "rmse_mean": f"{sum(rmse_vals)/len(rmse_vals):.8f}",
                    "bias_mean": f"{sum(bias_vals)/len(bias_vals):.8f}",
                }
            )

    print(f"[done] comparison rows: {compare_csv}")
    print(f"[done] best rows: {best_csv}")
    print(f"[done] aggregate summary: {summary_csv}")
    if have_mpl:
        print(f"[done] overlays: {plot_dir}")
    else:
        print("[warn] matplotlib unavailable; overlay plots skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
