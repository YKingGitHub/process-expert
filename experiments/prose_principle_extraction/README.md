# Prose Principle Extraction POC

Extract non-table prose knowledge from source PDF page images.

This fills the gap left by process-card-only VLM extraction: some useful knowledge, such as keyslot symmetry inspection with a dial indicator and gauge blocks, appears in surrounding prose rather than in the process-card table.

Run VLM extraction when an API key is available:

```bash
python3 experiments/prose_principle_extraction/scripts/vlm_extract_principles.py --pages 107
```

Validate the checked-in fixture:

```bash
python3 experiments/prose_principle_extraction/scripts/validate_principle_json.py \
  experiments/prose_principle_extraction/fixtures/source/p107_principles.json
python3 -m pytest experiments/prose_principle_extraction/tests -q
```
