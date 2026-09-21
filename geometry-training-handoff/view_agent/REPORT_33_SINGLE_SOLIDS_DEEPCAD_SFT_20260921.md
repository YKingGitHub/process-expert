# Ortho2CAD DeepCAD SFT checkpoint on 33 real drawing/STEP pairs

Date: 2026-09-21

## Conclusion

The DeepCAD-finetuned checkpoint does not generalize to this real industrial drawing set under the process-expert end-to-end protocol.

| Metric | DeepCAD SFT checkpoint | Qwen3-VL-8B base | Delta |
|---|---:|---:|---:|
| Valid STEP export | 1/33 (3.03%) | 8/33 (24.24%) | -21.21 pp |
| Strict geometry pass | 0/33 (0.00%) | 1/33 (3.03%) | -3.03 pp |
| Mean aligned IoU, all 33, invalid=0 | 0.001343 | 0.078014 | -0.076670 |
| Aligned IoU >= 0.5 | 0/33 (0.00%) | 2/33 (6.06%) | -6.06 pp |
| Mean aligned IoU, successfully scored STEP only | 0.044335 (n=1) | 0.429076 (n=6) | -0.384741 |

The strict pass requires all of the following: absolute volume error at most 2%, absolute surface-area error at most 5%, and maximum sorted bounding-box-axis error at most 2%.

The aligned IoU follows Ortho2CAD's principal-axis and scale normalization. It measures shape independently of absolute scale. The all-sample mean assigns zero to missing, invalid, failed, or timed-out predictions.

## Dataset construction

- Source archive: `图纸20260810.zip` (not committed; only aggregate, path-free results are published)
- SHA-256: `42413dae4b1744990e187b7944fe2a53835ce22411ce00b6c8a4d54226382ddc`
- 70 unambiguous PDF/STEP pairs were found. Among the 33 retained samples, 30 were paired by exact stem and 3 by unique part code.
- 33 single-solid pairs were retained for evaluation; 37 multi-solid/assembly pairs were excluded, and no invalid ground-truth STEP was found.
- The 33 cases contain 39 PDF-rendered input images at 200 DPI.
- Inference used an input-only manifest. Ground-truth STEP paths were kept in a separate evaluation-only manifest.

## Main evaluation protocol

- Checkpoint: `qwen3vl8b_deepcad_sft_5ep_a800x8`
- Input: one or more rendered engineering-drawing sheets per case.
- Output: CadQuery program, sandboxed execution, and STEP export.
- Decoding: deterministic, maximum 4096 new tokens, one execution-guided repair attempt.
- Image budget: 200704 to 1003520 pixels, matching the existing process-expert real-drawing baseline.
- CAD runtime: CadQuery 2.5.2.

The checkpoint exported one valid STEP, `case_009` (`STKJ-MT01-0023 排水管`). It did not pass any dimensional metric:

| Error for case_009 | Value |
|---|---:|
| Volume absolute error | 99.998427% |
| Surface-area absolute error | 99.988970% |
| Maximum bounding-box-axis error | 99.059633% |
| Scale-aligned IoU | 0.044335 |

The prediction had a bounding box near 1–2 units, while the ground truth was 57 x 57 x 178 mm.

## Failure analysis

- 32/33 cases failed to export a valid STEP.
- Final failure types: 30 syntax errors, one CadQuery vector/value error, and one nonexistent CadQuery API call.
- The checkpoint produced 65 total attempts across the original and repair passes. Median output length was 3644 tokens, and 28 attempts hit the 4096-token cap. The base model's median was 444 tokens.
- Generated programs visibly follow the normalized DeepCAD training representation: many small 0–1 coordinates, long sequences of reconstructed sketches, and repeated workplanes. They do not reliably read the millimetre dimensions in the annotated drawings.

This is a domain-shift failure. On the existing clean DeepCAD subset, the same checkpoint had 99/100 valid STEP files and an all-sample aligned IoU of 0.807751. On the real annotated drawing set, its all-sample aligned IoU fell to 0.001343.

## Native-training-protocol probe

Two cases were also tested with the exact short training prompt, the checkpoint's native 784–50176 pixel budget, 8192 output tokens, no repetition constraints, and no repair pass.

- `case_001`: generated all 8192 tokens and ended with an unclosed expression; no STEP.
- `case_009`: wrote a STEP, but strict OpenCascade validation reported an invalid solid; its aligned IoU was 0.020678.

This probe rules out the longer process-expert prompt and the 4096-token cap as the primary cause. A full 33-case native-protocol rerun was not performed because neither probe produced a usable CAD model.

## Artifacts

- Machine-readable aggregate: `results/deepcad_sft_real_drawings_20260921/summary.json`
- Path-free 33-case table: `results/deepcad_sft_real_drawings_20260921/per_case.csv`
- Persistent aligned-IoU evaluator: `evaluate_iou.py`
- GitHub Pages source: `../weekly-reports/2026-W39/index.html`

Raw drawings, ground-truth STEP files, checkpoints, generated programs, generated STEP files, and cluster-local paths are intentionally excluded from Git.

## Recommended next experiment

Do not continue tuning only on normalized, clean DeepCAD renders. Mix real annotated drawings into SFT, preserve physical millimetre scale in the target code, cap target program complexity, and validate generated code during dataset construction. Keep a held-out real-drawing validation set and select checkpoints on valid-STEP rate plus strict dimensional geometry, not only scale-normalized IoU.
