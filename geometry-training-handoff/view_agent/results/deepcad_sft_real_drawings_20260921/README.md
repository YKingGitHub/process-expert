# DeepCAD SFT checkpoint on real engineering drawings

This directory is the public, path-free snapshot for the 2026-09-21 Ortho2CAD evaluation. The full interpretation is in [`../../REPORT_33_SINGLE_SOLIDS_DEEPCAD_SFT_20260921.md`](../../REPORT_33_SINGLE_SOLIDS_DEEPCAD_SFT_20260921.md).

## Headline result

| Metric | DeepCAD SFT checkpoint | Qwen3-VL-8B base |
|---|---:|---:|
| Valid STEP export | 1/33 (3.03%) | 8/33 (24.24%) |
| Strict geometry pass | 0/33 (0.00%) | 1/33 (3.03%) |
| Mean aligned IoU, all samples and invalid=0 | 0.001343 | 0.078014 |
| IoU >= 0.5 | 0/33 (0.00%) | 2/33 (6.06%) |

The strict pass requires volume error <= 2%, surface-area error <= 5%, and maximum sorted bounding-box-axis error <= 2% at the same time. Aligned IoU removes pose and scale, matching the Ortho2CAD evaluation convention.

## Files

- `summary.json`: dataset construction, inference settings, aggregate metrics, failure analysis, and the native-protocol probe.
- `per_case.csv`: strict metrics and aligned IoU for all 33 cases, comparing the fine-tuned and base models.

The source drawings, ground-truth STEP files, checkpoints, generated programs, and generated STEP files are intentionally not included. This snapshot contains no cluster-local paths.
