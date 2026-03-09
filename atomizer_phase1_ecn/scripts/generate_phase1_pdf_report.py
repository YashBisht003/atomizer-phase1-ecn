#!/usr/bin/env python3
"""Generate a Phase-1 project PDF report."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--author", type=str, default="Yash Bisht", help="Author name")
    parser.add_argument(
        "--affiliation",
        type=str,
        default="Department of Mechanical and Industrial Engineering, Refrigeration Lab, IIT Roorkee",
        help="Author affiliation",
    )
    parser.add_argument("--out", type=Path, required=True, help="Output PDF path")
    return parser.parse_args()


def add_heading(story, styles, text: str):
    story.append(Paragraph(text, styles["Heading2"]))
    story.append(Spacer(1, 0.2 * cm))


def main() -> int:
    args = parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(args.out),
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
    )
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Atomizer High-Speed Imaging Project - Phase 1 Report", styles["Title"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"<b>Prepared by:</b> {args.author}", styles["Normal"]))
    story.append(Paragraph(f"<b>Affiliation:</b> {args.affiliation}", styles["Normal"]))
    story.append(Paragraph(f"<b>Date:</b> {date.today().isoformat()}", styles["Normal"]))
    story.append(Paragraph("<b>Platform:</b> PARAM Ganga HPC + Local Windows", styles["Normal"]))
    story.append(Spacer(1, 0.4 * cm))

    add_heading(story, styles, "1. Abstract")
    story.append(
        Paragraph(
            "This project established a complete, reproducible high-speed-imaging pipeline for atomizer "
            "analysis using publicly available ECN datasets. The workflow covers dataset discovery, HPC "
            "download, frame export, geometry extraction, sensitivity validation, and ECN reference comparison.",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 0.3 * cm))

    add_heading(story, styles, "2. Objective")
    story.append(
        Paragraph(
            "Create a practical baseline before lab experiments by extracting spray geometry metrics "
            "(penetration, cone angle, projected area) from benchmark high-speed videos and validating "
            "method robustness.",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 0.3 * cm))

    add_heading(story, styles, "3. Workflow Completed")
    steps = [
        "ECN links scraped and high-speed-only manifest created.",
        "Batch video download on HPC (13 files, ~170.7 MB).",
        "Frame export completed (191 frames).",
        "Geometry metrics extracted (177/191 valid frames).",
        "Sensitivity validation done (min-pixels and threshold sweeps).",
        "Reference comparison done (MAE/RMSE against Spray G reference curves).",
        "Final plots generated and results archived.",
    ]
    for s in steps:
        story.append(Paragraph(f"- {s}", styles["Normal"]))
    story.append(Spacer(1, 0.3 * cm))

    add_heading(story, styles, "4. Technical Notes")
    notes = [
        "OpenCV segmentation fault on HPC was resolved by switching to imageio backend.",
        "Frame overwrite bug (avi/gif name collision) was fixed by extension-specific output folders.",
        "All processing scripts are versioned in GitHub repository: YashBisht003/atomizer-phase1-ecn.",
    ]
    for n in notes:
        story.append(Paragraph(f"- {n}", styles["Normal"]))
    story.append(Spacer(1, 0.3 * cm))

    add_heading(story, styles, "5. Core Results")
    core_table = Table(
        [
            ["Metric", "Value"],
            ["Videos processed", "13"],
            ["Frames exported", "191"],
            ["Valid analysis frames", "177 / 191 (92.67%)"],
            ["Geometry outputs", "frame_metrics.csv, video_summary.csv"],
            ["Plot outputs", "Per-video + overview penetration/cone/area PNGs"],
        ],
        colWidths=[6.5 * cm, 10.5 * cm],
    )
    core_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF7")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    story.append(core_table)
    story.append(Spacer(1, 0.35 * cm))

    add_heading(story, styles, "6. Sensitivity (Validation Hardening)")
    sens_table = Table(
        [
            ["Variant", "Mean abs % change (Pen)", "Mean abs % change (Cone)", "Mean abs % change (Area)", "Delta OK frames"],
            ["minpix_30", "0.807", "0.855", "0.851", "+1"],
            ["minpix_90", "0.000", "0.000", "0.000", "0"],
            ["thr_30", "5.720", "9.072", "23.806", "0"],
            ["thr_45", "1.372", "2.184", "11.732", "0"],
        ],
        colWidths=[2.5 * cm, 3.3 * cm, 3.3 * cm, 3.3 * cm, 2.6 * cm],
    )
    sens_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF7")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ]
        )
    )
    story.append(sens_table)
    story.append(Spacer(1, 0.35 * cm))

    add_heading(story, styles, "7. ECN Reference Comparison (AVI)")
    ref_table = Table(
        [
            ["Subset", "Metric", "MAE mean", "RMSE mean", "Bias mean"],
            ["QSMS", "Cone Angle", "30.9354", "43.0165", "9.1661"],
            ["QSMS", "Penetration", "16.1530", "18.7094", "-0.2128"],
            ["HS_MOVIE", "Cone Angle", "31.9710", "41.7591", "3.5055"],
            ["HS_MOVIE", "Penetration", "18.7983", "22.6032", "-4.0703"],
        ],
        colWidths=[3.2 * cm, 3.2 * cm, 3.0 * cm, 3.0 * cm, 3.0 * cm],
    )
    ref_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF7")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (2, 1), (-1, -1), "CENTER"),
            ]
        )
    )
    story.append(ref_table)
    story.append(Spacer(1, 0.35 * cm))

    add_heading(story, styles, "8. Interpretation")
    points = [
        "Penetration is the most reliable validated metric in current Phase 1.",
        "Cone-angle error remains high for both subsets and needs method refinement.",
        "Sensitivity shows strong robustness to min-pixels and moderate sensitivity to threshold, especially for projected area.",
        "QSMS subset is preferred as primary benchmark for penetration validation.",
    ]
    for p in points:
        story.append(Paragraph(f"- {p}", styles["Normal"]))
    story.append(Spacer(1, 0.3 * cm))

    add_heading(story, styles, "9. Limitations and Next Steps")
    next_steps = [
        "Apply physical calibration (px-to-mm) from known lab scale/nozzle reference.",
        "Refine cone-angle extraction using fixed nozzle ROI and edge-based fitting.",
        "Lock baseline pipeline parameters (v1.0) and run unchanged on lab-captured videos.",
        "Report final MAE/RMSE with uncertainty bands for publication-quality results.",
    ]
    for p in next_steps:
        story.append(Paragraph(f"- {p}", styles["Normal"]))

    doc.build(story)
    print(f"[done] PDF written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
