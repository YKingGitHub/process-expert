#!/usr/bin/env bash
set -euo pipefail

view_partition="${1:-i64m1tga800u}"
view_memory="${VIEW_AGENT_MEMORY:-128G}"
if [[ "$view_partition" == "debug" ]]; then
  view_memory="${VIEW_AGENT_MEMORY:-64G}"
fi

exec srun \
  -p "$view_partition" \
  --gres=gpu:1 \
  --mem="$view_memory" \
  --cpus-per-task=8 \
  --pty bash
