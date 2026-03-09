#!/bin/bash
#SBATCH --job-name=atomizer_plots
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --time=01:00:00
#SBATCH --output=logs/plots_%j.out
#SBATCH --error=logs/plots_%j.err
##SBATCH --gres=gpu:1

set -euo pipefail

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate base

cd "$SLURM_SUBMIT_DIR"
if [ -d "atomizer_phase1_ecn/scripts" ]; then
  cd atomizer_phase1_ecn
fi

mkdir -p logs results/geometry/plots

if [ ! -f "results/geometry/frame_metrics.csv" ]; then
  echo "[error] results/geometry/frame_metrics.csv not found. Run geometry analysis first."
  exit 2
fi

if ! python - <<'PY'
import importlib.util
mods = ["matplotlib"]
missing = [m for m in mods if importlib.util.find_spec(m) is None]
if missing:
    raise SystemExit(1)
print("plot deps are present")
PY
then
  python -m pip install --user matplotlib
fi

python scripts/plot_geometry_metrics.py \
  --frame-csv results/geometry/frame_metrics.csv \
  --out-dir results/geometry/plots

echo "Done. Plot outputs at results/geometry/plots"
