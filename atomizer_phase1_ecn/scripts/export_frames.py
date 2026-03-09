#!/usr/bin/env python3
"""Export frames from high-speed videos to PNG images.

Default backend is `imageio` to avoid OpenCV binary crashes on some HPC nodes.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


VIDEO_EXTS = {".avi", ".mp4", ".mov", ".m4v", ".mkv", ".gif"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True, help="Root folder with videos")
    parser.add_argument("--output-dir", type=Path, required=True, help="Frame output folder")
    parser.add_argument("--step", type=int, default=5, help="Save every Nth frame")
    parser.add_argument("--max-videos", type=int, default=0, help="Optional cap for testing")
    parser.add_argument(
        "--backend",
        type=str,
        default="imageio",
        choices=["imageio", "opencv"],
        help="Decoding backend. Use imageio on HPC if OpenCV crashes.",
    )
    return parser.parse_args()


def list_videos(input_dir: Path) -> list[Path]:
    files = [p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS]
    return sorted(files)


def run_imageio_backend(args: argparse.Namespace, videos: list[Path]) -> int:
    try:
        import imageio.v2 as iio  # type: ignore
    except Exception as exc:  # pylint: disable=broad-except
        print("[error] imageio backend unavailable. Install with:")
        print("        python -m pip install --user imageio imageio-ffmpeg pillow")
        print(f"        detail: {exc}")
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "frame_export_report.csv"
    report_rows = []

    print(f"[info] backend=imageio videos queued: {len(videos)}")
    for i, video in enumerate(videos, start=1):
        rel = video.relative_to(args.input_dir)
        out_subdir = args.output_dir / rel.with_suffix("")
        out_subdir.mkdir(parents=True, exist_ok=True)

        status = "ok"
        fps = 0.0
        frame_idx = 0
        saved = 0
        try:
            reader = iio.get_reader(str(video))
            meta = reader.get_meta_data() or {}
            fps = float(meta.get("fps") or 0.0)

            for frame_idx, frame in enumerate(reader):
                if frame_idx % args.step == 0:
                    t_ms = (frame_idx / fps * 1000.0) if fps > 0 else 0.0
                    out_file = out_subdir / f"frame_{frame_idx:06d}_t{t_ms:010.3f}ms.png"
                    iio.imwrite(str(out_file), frame)
                    saved += 1
            frame_idx += 1 if saved > 0 or frame_idx > 0 else 0
            reader.close()
            print(f"[{i}/{len(videos)}] saved {saved} frames <- {video}")
        except Exception as exc:  # pylint: disable=broad-except
            status = "decode_failed"
            print(f"[warn] failed to decode: {video} ({exc})")

        report_rows.append(
            {
                "video_path": str(video),
                "status": status,
                "fps": fps,
                "total_frames_read": frame_idx,
                "saved_frames": saved,
            }
        )

    with report_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=["video_path", "status", "fps", "total_frames_read", "saved_frames"],
        )
        writer.writeheader()
        writer.writerows(report_rows)
    print(f"[done] report written: {report_path}")
    return 0


def run_opencv_backend(args: argparse.Namespace, videos: list[Path]) -> int:
    try:
        import cv2  # type: ignore
    except Exception as exc:  # pylint: disable=broad-except
        print("[error] OpenCV import failed. Install with:")
        print("        python -m pip install --user opencv-python-headless")
        print(f"        detail: {exc}")
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "frame_export_report.csv"
    report_rows = []

    print(f"[info] backend=opencv videos queued: {len(videos)}")
    for i, video in enumerate(videos, start=1):
        rel = video.relative_to(args.input_dir)
        out_subdir = args.output_dir / rel.with_suffix("")
        out_subdir.mkdir(parents=True, exist_ok=True)

        cap = cv2.VideoCapture(str(video))
        if not cap.isOpened():
            print(f"[warn] could not open: {video}")
            report_rows.append(
                {
                    "video_path": str(video),
                    "status": "open_failed",
                    "fps": 0.0,
                    "total_frames_read": 0,
                    "saved_frames": 0,
                }
            )
            continue

        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_idx = 0
        saved = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_idx % args.step == 0:
                t_ms = (frame_idx / fps * 1000.0) if fps > 0 else 0.0
                out_file = out_subdir / f"frame_{frame_idx:06d}_t{t_ms:010.3f}ms.png"
                cv2.imwrite(str(out_file), frame)
                saved += 1
            frame_idx += 1
        cap.release()

        print(f"[{i}/{len(videos)}] saved {saved} frames <- {video}")
        report_rows.append(
            {
                "video_path": str(video),
                "status": "ok",
                "fps": fps,
                "total_frames_read": frame_idx,
                "saved_frames": saved,
            }
        )

    with report_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=["video_path", "status", "fps", "total_frames_read", "saved_frames"],
        )
        writer.writeheader()
        writer.writerows(report_rows)
    print(f"[done] report written: {report_path}")
    return 0


def main() -> int:
    args = parse_args()

    if not args.input_dir.exists():
        print(f"[error] input dir not found: {args.input_dir}")
        return 2
    if args.step < 1:
        print("[error] --step must be >= 1")
        return 2

    videos = list_videos(args.input_dir)
    if args.max_videos > 0:
        videos = videos[: args.max_videos]
    if not videos:
        print("[error] no videos found")
        return 2

    if args.backend == "imageio":
        return run_imageio_backend(args, videos)
    return run_opencv_backend(args, videos)


if __name__ == "__main__":
    raise SystemExit(main())
