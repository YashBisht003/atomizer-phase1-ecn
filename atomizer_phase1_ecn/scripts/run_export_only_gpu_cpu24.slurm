#!/bin/bash
#SBATCH --job-name=atomizer_export_only
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --time=02:00:00
#SBATCH --output=logs/export_only_%j.out
#SBATCH --error=logs/export_only_%j.err
##SBATCH --gres=gpu:1

set -euo pipefail

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate base

cd "$SLURM_SUBMIT_DIR"
if [ -d "atomizer_phase1_ecn/scripts" ]; then
  cd atomizer_phase1_ecn
fi

mkdir -p logs data/frames

if ! python - <<'PY'
import importlib.util
mods = ["imageio", "imageio_ffmpeg", "PIL"]
missing = [m for m in mods if importlib.util.find_spec(m) is None]
if missing:
    raise SystemExit(1)
print("frame-export deps are present")
PY
then
  python -m pip install --user imageio imageio-ffmpeg pillow
fi

python scripts/export_frames.py \
  --input-dir data/raw \
  --output-dir data/frames \
  --step 5 \
  --backend imageio
