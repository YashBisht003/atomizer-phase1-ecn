# Atomizer Phase 1 (High-Speed Imaging Only)

This folder gives you a reproducible Phase 1 workflow for:

1. Collecting direct ECN dataset file links.
2. Downloading files in batch.
3. Exporting frames from high-speed videos.

## 0) Folder Layout

- `manifests/seed_pages.txt`: ECN pages to scrape for downloadable files.
- `manifests/ecn_links.csv`: generated file manifest with direct URLs.
- `manifests/ecn_highspeed_links.csv`: generated video-only manifest (`.avi/.mp4/.gif`).
- `scripts/extract_ecn_links.py`: builds the URL manifest.
- `scripts/download_manifest.py`: downloads all URLs from the manifest.
- `scripts/export_frames.py`: exports frames from downloaded videos.
- `scripts/analyze_spray_geometry.py`: computes penetration/cone/area metrics from frames.
- `data/raw/`: downloaded files.
- `data/frames/`: exported frame images.
- `results/geometry/`: analysis CSV outputs.

## 1) Windows Local (PowerShell)

From this folder (`atomizer_phase1_ecn`), run:

```powershell
python .\scripts\extract_ecn_links.py `
  --seed-file .\manifests\seed_pages.txt `
  --out-csv .\manifests\ecn_links.csv
```

```powershell
python .\scripts\make_highspeed_manifest.py `
  --in-csv .\manifests\ecn_links.csv `
  --out-csv .\manifests\ecn_highspeed_links.csv
```

```powershell
python .\scripts\download_manifest.py `
  --manifest .\manifests\ecn_highspeed_links.csv `
  --out-dir .\data\raw `
  --workers 6
```

```powershell
python .\scripts\export_frames.py `
  --input-dir .\data\raw `
  --output-dir .\data\frames `
  --step 5
```

One-command wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_phase1_windows.ps1 -MaxFiles 0 -Step 5 -Workers 6
```

## 2) PARAM Ganga (Linux) Recommended

Copy this folder to your HPC login node, then run:

```bash
cd atomizer_phase1_ecn
python3 scripts/extract_ecn_links.py \
  --seed-file manifests/seed_pages.txt \
  --out-csv manifests/ecn_links.csv
```

```bash
python3 scripts/make_highspeed_manifest.py \
  --in-csv manifests/ecn_links.csv \
  --out-csv manifests/ecn_highspeed_links.csv
```

```bash
python3 scripts/download_manifest.py \
  --manifest manifests/ecn_highspeed_links.csv \
  --out-dir data/raw \
  --workers 8
```

```bash
python3 scripts/export_frames.py \
  --input-dir data/raw \
  --output-dir data/frames \
  --step 5
```

If OpenCV crashes on your HPC node, use imageio backend:

```bash
python3 -m pip install --user imageio imageio-ffmpeg pillow
python3 scripts/export_frames.py \
  --input-dir data/raw \
  --output-dir data/frames \
  --step 5 \
  --backend imageio
```

To re-export cleanly (recommended after script updates):

```bash
rm -rf data/frames
mkdir -p data/frames
```

Batch mode (SLURM, `gpu` partition, 24 CPU cores, no memory flag):

```bash
sbatch scripts/run_phase1_gpu_cpu24.slurm
squeue -u "$USER"
```

Resume only frame export (if download already finished):

```bash
sbatch scripts/run_export_only_gpu_cpu24.slurm
```

Run geometry analysis from existing frames:

```bash
sbatch scripts/run_geometry_analysis_gpu_cpu24.slurm
```

Create report plots from geometry CSV:

```bash
sbatch scripts/run_geometry_plots_gpu_cpu24.slurm
```

Check logs:

```bash
ls -lah logs
tail -n 100 logs/phase1_<jobid>.out
tail -n 100 logs/phase1_<jobid>.err
```

Analysis outputs:

```bash
ls -lah results/geometry
head -n 5 results/geometry/video_summary.csv
head -n 5 results/geometry/frame_metrics.csv
ls -lah results/geometry/plots
```

Transfer example from Windows (PowerShell + OpenSSH):

```powershell
scp -r .\atomizer_phase1_ecn <your_user>@<ganga_login_host>:~/atomizer_phase1_ecn
```

If your HPC has no OpenCV, install in user space:

```bash
python3 -m pip install --user opencv-python-headless
```

## 3) Fast Smoke Test (Small Run)

Use limits first before full download:

```powershell
python .\scripts\download_manifest.py `
  --manifest .\manifests\ecn_links.csv `
  --out-dir .\data\raw `
  --allow-ext .txt,.csv `
  --max-files 3
```

Useful filters:

- `--allow-ext .avi,.mp4` to fetch only videos.
- `--contains spray-a` to limit by URL substring.

Create the video-only manifest after extraction:

```powershell
python .\scripts\make_highspeed_manifest.py `
  --in-csv .\manifests\ecn_links.csv `
  --out-csv .\manifests\ecn_highspeed_links.csv
```

## 4) Notes

- This workflow is high-speed imaging only (no PDPA dependencies).
- URLs are scraped from ECN pages and deduplicated automatically.
- Some links may fail if external hosts are down; failures are logged in `download_failures.csv`.
