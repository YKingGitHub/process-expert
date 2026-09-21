#!/usr/bin/env bash
#SBATCH --job-name=view-agent-33
#SBATCH --partition=i64m1tga40u,i64m1tga800u
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=04:00:00
#SBATCH --output=geometry-training-handoff/view_agent/runs/slurm-batch-%j.log

set -euo pipefail

view_agent_dir="${VIEW_AGENT_DIR:-${SLURM_SUBMIT_DIR:?}/geometry-training-handoff/view_agent}"
view_python="${VIEW_AGENT_PYTHON:-/hpc2hdd/home/lwang592/projects/.venvs/process-view-agent/bin/python}"
view_cad_python="${VIEW_AGENT_CAD_PYTHON:-/hpc2hdd/home/lwang592/projects/.venvs/process-view-agent-cad/bin/python}"
view_model="${1:?usage: submit_batch.sbatch MODEL OUTPUT_DIR INFERENCE_MANIFEST EVALUATION_MANIFEST}"
view_output="${2:?usage: submit_batch.sbatch MODEL OUTPUT_DIR INFERENCE_MANIFEST EVALUATION_MANIFEST}"
view_inference_manifest="${3:?usage: submit_batch.sbatch MODEL OUTPUT_DIR INFERENCE_MANIFEST EVALUATION_MANIFEST}"
view_evaluation_manifest="${4:?usage: submit_batch.sbatch MODEL OUTPUT_DIR INFERENCE_MANIFEST EVALUATION_MANIFEST}"
view_shard_count="${VIEW_AGENT_SHARD_COUNT:-1}"
view_shard_index="${VIEW_AGENT_SHARD_INDEX:-0}"

export PYTHONUNBUFFERED=1

"$view_python" "$view_agent_dir/check_env.py" \
  --model "$view_model" \
  --cad-python "$view_cad_python" \
  --require-cuda

"$view_python" "$view_agent_dir/batch_view_agent.py" \
  --manifest "$view_inference_manifest" \
  --output-dir "$view_output" \
  --model "$view_model" \
  --cad-python "$view_cad_python" \
  --max-new-tokens "${VIEW_AGENT_MAX_NEW_TOKENS:-4096}" \
  --repetition-penalty "${VIEW_AGENT_REPETITION_PENALTY:-1.05}" \
  --no-repeat-ngram-size "${VIEW_AGENT_NO_REPEAT_NGRAM_SIZE:-16}" \
  --min-pixels "${VIEW_AGENT_MIN_PIXELS:-200704}" \
  --max-pixels "${VIEW_AGENT_MAX_PIXELS:-1003520}" \
  --repair-attempts "${VIEW_AGENT_REPAIR_ATTEMPTS:-1}" \
  --shard-count "$view_shard_count" \
  --shard-index "$view_shard_index"

if [[ "${VIEW_AGENT_SKIP_EVALUATION:-0}" != "1" ]]; then
  "$view_cad_python" "$view_agent_dir/evaluate_batch.py" \
    --manifest "$view_evaluation_manifest" \
    --generation-dir "$view_output"
fi
