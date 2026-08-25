#!/usr/bin/env bash
set -euo pipefail

view_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
view_agent_dir="$(cd "$view_script_dir/.." && pwd)"
view_handoff_dir="$(cd "$view_agent_dir/.." && pwd)"
view_python="${VIEW_AGENT_PYTHON:-/hpc2hdd/home/lwang592/projects/.venvs/process-view-agent/bin/python}"
view_cad_python="${VIEW_AGENT_CAD_PYTHON:-/hpc2hdd/home/lwang592/projects/.venvs/process-view-agent-cad/bin/python}"
view_model="${VIEW_AGENT_MODEL:-/hpc2hdd/home/lwang592/projects/.models/Qwen3-VL-8B-Instruct}"
view_max_tokens="${VIEW_AGENT_MAX_NEW_TOKENS:-1024}"
view_max_pixels="${VIEW_AGENT_MAX_PIXELS:-1003520}"
view_image="${1:-$view_handoff_dir/drawings/端盖.png}"
view_output="${2:-$view_agent_dir/runs/debug-smoke}"

exec srun \
  --job-name=view-agent-debug \
  -p debug \
  --gres=gpu:1 \
  --mem=64G \
  --cpus-per-task=8 \
  --time=00:30:00 \
  "$view_python" "$view_agent_dir/view_agent.py" \
  --model "$view_model" \
  --cad-python "$view_cad_python" \
  --image "$view_image" \
  --output-dir "$view_output" \
  --max-new-tokens "$view_max_tokens" \
  --max-pixels "$view_max_pixels" \
  --execute
