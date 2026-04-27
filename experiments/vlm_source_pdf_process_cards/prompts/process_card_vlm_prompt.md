You are extracting machining process cards from a scanned/rendered PDF page image.

Return only one JSON object. Do not include markdown, comments, or explanatory text.

The output schema is:

{
  "source_page": 0,
  "page_title": "",
  "cards": [
    {
      "part_name": "",
      "table_no": "",
      "table_title": "",
      "is_continuation": false,
      "continuation_of": "",
      "technical_requirements": [],
      "steps": [
        {
          "step_no": 0,
          "operation_name": "",
          "operation_content": "",
          "equipment": "",
          "dimensions": [
            {
              "surface": "inner|outer|length|hole|slot|unknown",
              "nominal": 0.0,
              "unit": "mm",
              "upper_deviation": null,
              "lower_deviation": null,
              "tolerance_text": "",
              "source_text": ""
            }
          ],
          "allowances": [
            {
              "allowance_type": "machining|grinding|finishing|unknown",
              "value": 0.0,
              "max_value": null,
              "unit": "mm",
              "source_text": ""
            }
          ]
        }
      ]
    }
  ],
  "warnings": []
}

Rules:

1. Extract only visible information from the page image. Do not infer missing dimensions.
2. Preserve table row order and step numbers exactly.
3. If the page is a continuation table, set `is_continuation=true` and preserve the visible continuation marker.
4. For dimensions, preserve `source_text` exactly as visible, including `φ`, `±`, superscript/subscript-style deviations, and units.
5. Convert tolerances into numeric deviations:
   - `±0.05` means `upper_deviation=0.05`, `lower_deviation=-0.05`.
   - `+0.08/0` means `upper_deviation=0.08`, `lower_deviation=0`.
   - `+0.08/+0.04` means `upper_deviation=0.08`, `lower_deviation=0.04`.
   - `0/-0.043` means `upper_deviation=0`, `lower_deviation=-0.043`.
6. If a dimension says "to drawing requirement" without a visible numeric target, keep the text in `operation_content` but do not invent a dimension.
7. Equipment is the rightmost table column. Preserve model numbers such as `CA6140`, `M1432A`, `中心架`, `专用工装`.
8. Use empty arrays for absent dimensions or allowances.
9. Use `null` for unknown numeric deviations, not an empty string.
