#!/usr/bin/env bash
#SBATCH --job-name=view-agent-smoke
#SBATCH --partition=i64m1tga800u
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=02:00:00
#SBATCH --output=view-agent-%j.log

set -euo pipefail

view_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
view_agent_dir="$(cd "$view_script_dir/.." && pwd)"
view_handoff_dir="$(cd "$view_agent_dir/.." && pwd)"
view_python="${VIEW_AGENT_PYTHON:-/hpc2hdd/home/lwang592/projects/.venvs/process-view-agent/bin/python}"
view_cad_python="${VIEW_AGENT_CAD_PYTHON:-/hpc2hdd/home/lwang592/projects/.venvs/process-view-agent-cad/bin/python}"
view_model="${VIEW_AGENT_MODEL:-/hpc2hdd/home/lwang592/projects/.models/Qwen3-VL-8B-Instruct}"
view_image="${1:-$view_handoff_dir/drawings/端盖.png}"
view_output="${2:-$view_agent_dir/runs/slurm-${SLURM_JOB_ID}}"

"$view_python" "$view_agent_dir/check_env.py" \
  --model "$view_model" \
  --cad-python "$view_cad_python" \
  --require-cuda
"$view_python" "$view_agent_dir/view_agent.py" \
  --model "$view_model" \
  --cad-python "$view_cad_python" \
  --image "$view_image" \
  --output-dir "$view_output" \
  --max-new-tokens 4096 \
  --execute
