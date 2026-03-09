#!/bin/bash
#SBATCH --job-name=atomizer_geometry
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --time=02:00:00
#SBATCH --output=logs/geometry_%j.out
#SBATCH --error=logs/geometry_%j.err
##SBATCH --gres=gpu:1

set -euo pipefail

echo "SLURM_JOBID=$SLURM_JOBID"
echo "SLURM_JOB_NODELIST=$SLURM_JOB_NODELIST"
echo "SLURM_NTASKS=$SLURM_NTASKS"
echo "SLURM_CPUS_PER_TASK=$SLURM_CPUS_PER_TASK"
echo "SLURM_SUBMIT_DIR=$SLURM_SUBMIT_DIR"

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate base

cd "$SLURM_SUBMIT_DIR"
if [ -d "atomizer_phase1_ecn/scripts" ]; then
  cd atomizer_phase1_ecn
fi

mkdir -p logs results/geometry

if [ ! -d "data/frames" ]; then
  echo "[error] data/frames not found. Run frame export first."
  exit 2
fi

if ! python - <<'PY'
import importlib.util
mods = ["numpy", "imageio", "PIL"]
missing = [m for m in mods if importlib.util.find_spec(m) is None]
if missing:
    raise SystemExit(1)
print("analysis deps are present")
PY
then
  python -m pip install --user numpy imageio pillow
fi

python scripts/analyze_spray_geometry.py \
  --frames-dir data/frames \
  --out-dir results/geometry \
  --px-to-mm 1.0 \
  --min-pixels 60

echo "Done. Outputs:"
echo "  results/geometry/frame_metrics.csv"
echo "  results/geometry/video_summary.csv"
