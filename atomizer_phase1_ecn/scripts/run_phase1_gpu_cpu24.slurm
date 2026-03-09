#!/bin/bash
#SBATCH --job-name=atomizer_phase1
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --time=06:00:00
#SBATCH --output=logs/phase1_%j.out
#SBATCH --error=logs/phase1_%j.err
##SBATCH --gres=gpu:1

set -euo pipefail

echo "SLURM_JOBID=$SLURM_JOBID"
echo "SLURM_JOB_NODELIST=$SLURM_JOB_NODELIST"
echo "SLURM_NTASKS=$SLURM_NTASKS"
echo "SLURM_CPUS_PER_TASK=$SLURM_CPUS_PER_TASK"
echo "SLURM_SUBMIT_DIR=$SLURM_SUBMIT_DIR"

# Activate conda base as requested
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate base

cd "$SLURM_SUBMIT_DIR"
# If submitted from repo root, move into project folder.
if [ -d "atomizer_phase1_ecn/scripts" ]; then
  cd atomizer_phase1_ecn
fi

mkdir -p logs data/raw data/frames

python scripts/extract_ecn_links.py \
  --seed-file manifests/seed_pages.txt \
  --out-csv manifests/ecn_links.csv

python scripts/make_highspeed_manifest.py \
  --in-csv manifests/ecn_links.csv \
  --out-csv manifests/ecn_highspeed_links.csv

python scripts/download_manifest.py \
  --manifest manifests/ecn_highspeed_links.csv \
  --out-dir data/raw \
  --workers "${SLURM_CPUS_PER_TASK}"

python scripts/export_frames.py \
  --input-dir data/raw \
  --output-dir data/frames \
  --step 5

echo "Done. Key outputs:"
echo "  manifests/ecn_highspeed_links.csv"
echo "  data/raw"
echo "  data/frames/frame_export_report.csv"
