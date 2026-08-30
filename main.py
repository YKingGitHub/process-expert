#!/usr/bin/env python3
"""
工艺卡生成 DEMO — 主入口

5 阶段流水线:
  Stage 1: 图纸解析 (VLM)
  Stage 2: 通用工艺框架检索 (LLM/Web)
  Stage 3: 知识库定向检索 (PostgreSQL)
  Stage 4: 工艺路线生成 (LLM)
  Stage 5: 工艺卡渲染 (python-docx)

用法:
  python3 main.py \
    --drawing <图纸路径.png> \
    --blank-info "⌀50×100, L为零件长度" \
    --equipment "数控车床, 三轴加工中心, 车床" \
    --material "45钢" \
    --output output/
"""

import argparse
import sys
import uuid
from datetime import datetime
from pathlib import Path

import yaml

from tracer.pipeline_tracer import PipelineTracer
from stages.stage1_drawing_analysis import analyze_drawing
from stages.stage2_web_research import research_process_framework
from stages.stage3_kb_search import search_knowledge_base
from stages.stage4_route_generation import generate_process_route
from stages.stage5_card_rendering import render_process_card
from stages.cad_json_parser import parse_cad_json


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="工艺卡生成 DEMO")
    parser.add_argument("--drawing", required=True, help="工程图纸路径 (PNG/JPG)")
    parser.add_argument("--blank-info", required=True, help="毛坯信息，如 '⌀50×100'")
    parser.add_argument("--equipment", required=True, help="可用设备，逗号分隔")
    parser.add_argument("--material", required=True, help="材料牌号，如 '45钢'")
    parser.add_argument("--cad-json", default=None, help="CAD模型JSON文件路径（可选，提供精确几何数据）")
    parser.add_argument("--output", default="output", help="输出目录")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    args = parser.parse_args()

    # Validate input
    drawing_path = Path(args.drawing)
    if not drawing_path.exists():
        print(f"ERROR: 图纸文件不存在: {args.drawing}")
        sys.exit(1)

    config = load_config(args.config)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize tracer
    tracer = PipelineTracer()
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    tracer.start(run_id, f"图纸={drawing_path.name}, 材料={args.material}, 毛坯={args.blank_info}")

    print(f"{'='*60}")
    print(f"工艺卡生成 DEMO — Run ID: {run_id}")
    print(f"{'='*60}")

    # =========================================================
    # Stage 1: 图纸解析
    # =========================================================
    print(f"\n[Stage 1] 图纸解析 (VLM)...")
    try:
        part_features = analyze_drawing(str(drawing_path), config, tracer)
        part_type = part_features.get("part_type", "未识别")
        print(f"  → 零件类型: {part_type}")
        print(f"  → 识别特征: {len(part_features.get('features', []))} 项")
    except Exception as e:
        print(f"  → ERROR: {e}")
        part_features = {"part_type": "回转体零件", "features": [], "_error": str(e)}
        part_type = "回转体零件"
        tracer.log_error(str(e))
        tracer.end_stage(part_features)

    # =========================================================
    # Stage 1.5: CAD JSON 增强（如果提供）
    # =========================================================
    if args.cad_json:
        cad_path = Path(args.cad_json)
        if cad_path.exists():
            print(f"\n[Stage 1.5] CAD JSON 精确数据增强...")
            try:
                cad_features = parse_cad_json(str(cad_path))
                # Merge CAD precise data into VLM results
                if cad_features.get("main_dimensions"):
                    part_features["cad_dimensions"] = cad_features["main_dimensions"]
                if cad_features.get("features"):
                    part_features["cad_features"] = cad_features["features"]
                if cad_features.get("tolerances"):
                    part_features["cad_tolerances"] = cad_features["tolerances"]
                if cad_features.get("manufacturing_sequence"):
                    part_features["cad_sequence"] = cad_features["manufacturing_sequence"]
                print(f"  → CAD 尺寸: {len(cad_features.get('main_dimensions', {}))} 项")
                print(f"  → CAD 特征: {len(cad_features.get('features', []))} 项")
                print(f"  → CAD 公差: {len(cad_features.get('tolerances', []))} 项")
            except Exception as e:
                print(f"  → WARNING: CAD JSON 解析失败: {e}")
        else:
            print(f"\n  WARNING: CAD JSON 文件不存在: {args.cad_json}")

    # =========================================================
    # Stage 2: 通用工艺框架检索
    # =========================================================
    print(f"\n[Stage 2] 通用工艺框架检索...")
    try:
        material = args.material
        framework = research_process_framework(part_type, material, config, tracer)
        seq_count = len(framework.get("typical_sequence", []))
        print(f"  → 典型工序: {seq_count} 道")
        for s in framework.get("typical_sequence", []):
            print(f"     - {s.get('op_name', '?')}: {', '.join(s.get('key_points', [])[:2])}")
    except Exception as e:
        print(f"  → ERROR: {e}")
        framework = {"typical_sequence": [], "quality_notes": []}
        tracer.log_error(str(e))
        tracer.end_stage(framework)

    # =========================================================
    # Stage 3: 知识库定向检索
    # =========================================================
    print(f"\n[Stage 3] 知识库定向检索 (PostgreSQL)...")
    try:
        op_types = [s.get("op_name", "") for s in framework.get("typical_sequence", [])]
        kb_results = search_knowledge_base(args.material, op_types, config, tracer)
        param_count = sum(len(v) for v in kb_results.get("params", {}).values())
        exp_count = len(kb_results.get("experiences", []))
        print(f"  → 切削参数: {param_count} 条")
        print(f"  → 加工经验: {exp_count} 条")
    except Exception as e:
        print(f"  → ERROR: {e}")
        kb_results = {"params": {}, "experiences": []}
        tracer.log_error(str(e))
        tracer.end_stage(kb_results)

    # =========================================================
    # Stage 4: 工艺路线生成
    # =========================================================
    print(f"\n[Stage 4] 工艺路线生成 (LLM)...")
    try:
        process_route = generate_process_route(
            part_features=part_features,
            process_framework=framework,
            kb_results=kb_results,
            blank_info=args.blank_info,
            equipment=args.equipment,
            material=args.material,
            config=config,
            tracer=tracer,
        )
        print(f"  → 生成工序: {len(process_route)} 道")
        for step in process_route:
            print(f"     - {step.get('seq', '?')} {step.get('op_name', '?')}: {step.get('equipment', '-')}")
    except Exception as e:
        print(f"  → ERROR: {e}")
        process_route = []
        tracer.log_error(str(e))
        tracer.end_stage(process_route)

    # =========================================================
    # Stage 5: 工艺卡渲染
    # =========================================================
    print(f"\n[Stage 5] 工艺卡渲染 (Word)...")
    if not process_route:
        print("  → SKIP: 无工艺路线数据，跳过渲染")
        docx_path = None
    else:
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            docx_output = str(output_dir / f"工艺卡_{ts}.docx")
            part_info = {
                "part_type": part_type,
                "material": args.material,
                "blank_info": args.blank_info,
            }
            docx_path = render_process_card(process_route, part_info, docx_output, tracer)
            print(f"  → 输出: {docx_path}")
        except Exception as e:
            print(f"  → ERROR: {e}")
            docx_path = None
            tracer.log_error(str(e))
            tracer.end_stage(None)

    # =========================================================
    # Finish: 输出 Trace
    # =========================================================
    json_path, md_path = tracer.finish(str(output_dir))

    print(f"\n{'='*60}")
    print(f"完成!")
    print(f"{'='*60}")
    if docx_path:
        print(f"  工艺卡: {docx_path}")
    print(f"  Trace JSON: {json_path}")
    print(f"  Trace 报告: {md_path}")

    if not process_route:
        print(f"\n  WARNING: 工艺路线生成失败，未生成工艺卡文件。请检查 Trace 报告定位问题。")
        sys.exit(1)


if __name__ == "__main__":
    main()
