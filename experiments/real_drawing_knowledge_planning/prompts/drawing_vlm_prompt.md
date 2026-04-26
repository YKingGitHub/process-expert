You are extracting manufacturing-relevant information from a mechanical drawing image.

Return only one JSON object. Do not include markdown, comments, or explanatory text.

The output schema is:

{
  "source_file": "",
  "extraction_mode": "drawing_png_vlm",
  "part": {
    "part_category": "",
    "material": "",
    "blank": ""
  },
  "overall_geometry": "",
  "dimensions": [
    {
      "name": "",
      "value": "",
      "unit": "mm",
      "tolerance": "",
      "source_text": ""
    }
  ],
  "features": [
    {
      "name": "",
      "feature_type": "",
      "description": "",
      "related_dimensions": [],
      "source_text": ""
    }
  ],
  "datums": [
    {
      "name": "",
      "description": "",
      "source_text": ""
    }
  ],
  "geometric_tolerances": [
    {
      "type": "",
      "value": "",
      "datums": [],
      "applies_to": "",
      "source_text": ""
    }
  ],
  "surface_roughness": [
    {
      "value": "",
      "applies_to": "",
      "source_text": ""
    }
  ],
  "technical_requirements": [],
  "manufacturing_notes": [],
  "warnings": []
}

Rules:

1. Extract only visible information from the drawing. Do not invent material or blank details if not shown.
2. Preserve key dimension and tolerance source text exactly when possible, including `φ`, `+0.25/0`, `+0.3/0`, and datum labels.
3. Capture geometric tolerance frames such as position tolerance with datum references.
4. Capture surface roughness marks and technical requirement text.
5. If a field is not visible, use an empty string or empty array and add a warning only if it affects manufacturing planning.
