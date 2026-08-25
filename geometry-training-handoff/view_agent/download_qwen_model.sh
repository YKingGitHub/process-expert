#!/usr/bin/env bash
set -euo pipefail

view_model="${1:-Qwen3-VL-8B-Instruct}"
view_root="${VIEW_AGENT_MODEL_ROOT:-/hpc2hdd/home/lwang592/projects/.models}"
view_dir="$view_root/$view_model"
view_base="https://www.modelscope.cn/models/Qwen/$view_model/resolve/master"
view_metadata=(
  chat_template.json
  config.json
  generation_config.json
  merges.txt
  preprocessor_config.json
  tokenizer.json
  tokenizer_config.json
  video_preprocessor_config.json
  vocab.json
)

case "$view_model" in
  Qwen3-VL-2B-Instruct)
    view_weights=(model.safetensors)
    view_hashes=(7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0)
    ;;
  Qwen3-VL-8B-Instruct)
    view_metadata+=(model.safetensors.index.json)
    view_weights=(
      model-00001-of-00004.safetensors
      model-00002-of-00004.safetensors
      model-00003-of-00004.safetensors
      model-00004-of-00004.safetensors
    )
    view_hashes=(
      d5d0aef0eb170fc7453a296c43c0849a56f510555d3588e4fd662bb35490aefa
      8be88fb5501e4d5719a6d4cc212e6a13480330e74f3e8c77daa1a68f199106b5
      83de00eafe6e0d57ccd009dbcf71c9974d74df2f016c27afb7e95aafd16b2192
      0a88b98e9f96270973f567e6a2c103ede6ccdf915ca3075e21c755604d0377a5
    )
    ;;
  *)
    echo "unsupported model: $view_model" >&2
    exit 2
    ;;
esac

mkdir -p "$view_dir"
for view_file in "${view_metadata[@]}"; do
  curl -fL --retry 20 --connect-timeout 20 --max-time 1800 \
    -o "$view_dir/$view_file" "$view_base/$view_file"
done

for view_index in "${!view_weights[@]}"; do
  view_file="${view_weights[$view_index]}"
  aria2c -c -x 8 -s 8 -k 16M --retry-wait=5 --max-tries=0 \
    --connect-timeout=20 --timeout=60 --lowest-speed-limit=10K \
    --console-log-level=warn --summary-interval=30 \
    -d "$view_dir" -o "$view_file" "$view_base/$view_file"
  if [[ "${VIEW_AGENT_VERIFY:-1}" == "1" ]]; then
    echo "${view_hashes[$view_index]}  $view_dir/$view_file" | sha256sum -c -
  fi
done

echo "model ready: $view_dir"
