# Source-PDF VLM Process Card Experiment

## Purpose

Validate process-card extraction directly from source PDF page images, instead of trusting the previous POC database as ground truth.

The previous deterministic-calculation POC used:

```text
/root/process-expert/output/unified_extract.db
```

That is useful as an exploration input, but it is not a reliable gold source. A direct check against the PDF shows at least one meaningful error:

```text
PDF p108:  φ279.2 ±0.05 mm, φ300.8 ±0.05 mm
POC DB:    φ279.2 +0.05 mm, φ300.8 +0.05 mm
```

For deterministic calculations, this matters because `±0.05` and `+0.05/0` lead to different lower deviations.

## Test Pages

Source PDF:

```text
references/工艺知识库.pdf
```

Pages:

- p106-107: output shaft process card
- p108: cylinder liner process card
- p109-110: seal positioning sleeve process card

## Workflow

```text
source PDF pages
  -> render page PNG
  -> VLM extracts strict JSON
  -> local schema validation
  -> compare with manual gold samples and old POC DB
  -> deterministic calculation only after extraction passes
```

## Commands

Render source pages:

```bash
python3 experiments/vlm_source_pdf_process_cards/scripts/render_pages.py
```

Validate manual gold:

```bash
python3 experiments/vlm_source_pdf_process_cards/scripts/validate_process_card_json.py \
  experiments/vlm_source_pdf_process_cards/fixtures/gold/p108_cylinder_liner.json
```

Compare manual gold with the old POC fixture:

```bash
python3 experiments/vlm_source_pdf_process_cards/scripts/compare_gold_to_poc.py
```

Run VLM extraction if `DASHSCOPE_API_KEY` is available:

```bash
python3 experiments/vlm_source_pdf_process_cards/scripts/vlm_extract_process_cards.py \
  --pages 106 107 108 109 110
```

By default the script also tries `/opt/ai-stack/compose/.env` for `DASHSCOPE_API_KEY`.

The VLM script writes JSON to:

```text
experiments/vlm_source_pdf_process_cards/output/
```

## Current Judgment

This experiment is meant to answer a different question from the first POC:

- first POC: can Python calculate if the content is already structured enough?
- this POC: can source-PDF visual extraction produce calculation-grade structured content?

The second question must be answered before treating extracted process cards as trusted calculation inputs.
