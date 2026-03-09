#!/bin/bash
#SBATCH --job-name=atomizer_refcmp
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --time=02:00:00
#SBATCH --output=logs/refcmp_%j.out
#SBATCH --error=logs/refcmp_%j.err
##SBATCH --gres=gpu:1

set -euo pipefail

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate base

cd "$SLURM_SUBMIT_DIR"
if [ -d "atomizer_phase1_ecn/scripts" ]; then
  cd atomizer_phase1_ecn
fi

mkdir -p logs results/reference_compare

if [ ! -f "results/geometry/frame_metrics.csv" ]; then
  echo "[error] results/geometry/frame_metrics.csv missing. Run geometry analysis first."
  exit 2
fi

# Pull Spray G reference txt files (small files only).
python scripts/download_manifest.py \
  --manifest manifests/ecn_links.csv \
  --out-dir data/raw \
  --workers 8 \
  --allow-ext .txt \
  --contains cvdata/assets/datafiles/pen/Spray_G

if ! python - <<'PY'
import importlib.util
mods = ["numpy", "matplotlib"]
missing = [m for m in mods if importlib.util.find_spec(m) is None]
if missing:
    raise SystemExit(1)
print("reference-compare deps are present")
PY
then
  python -m pip install --user numpy matplotlib
fi

python scripts/compare_with_reference.py \
  --frame-csv results/geometry/frame_metrics.csv \
  --reference-dir data/raw/ecn.sandia.gov/cvdata/assets/datafiles/pen \
  --out-dir results/reference_compare \
  --include-regex "__avi$"

echo "Done. Outputs:"
echo "  results/reference_compare/comparison_rows.csv"
echo "  results/reference_compare/best_rows.csv"
echo "  results/reference_compare/aggregate_summary.csv"
