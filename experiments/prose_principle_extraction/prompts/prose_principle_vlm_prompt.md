You are extracting machining process knowledge from non-table prose on a rendered PDF page image.

Return only one JSON object. Do not include markdown, comments, or explanatory text.

The output schema is:

{
  "source_page": 0,
  "page_title": "",
  "principle_records": [
    {
      "id": "",
      "topic": "",
      "principle_type": "inspection_method|datum_selection|operation_sequence|thin_wall_processing|heat_treatment_arrangement|process_route_planning|unknown",
      "principle_text": "",
      "applicable_scenario": "",
      "source_text": "",
      "evidence_region": "",
      "confidence": 0.0,
      "tags": [],
      "quality_flags": []
    }
  ],
  "warnings": []
}

Rules:

1. Extract only visible non-table prose. Do not extract table rows as principle records.
2. Preserve `source_text` as a direct visible text span from the page as much as possible.
3. Prefer short, atomic records that answer a specific Agent query.
4. If the page contains a keyslot symmetry inspection method, extract it.
5. If evidence is incomplete or ambiguous, keep the record but add a quality flag.
6. Use empty arrays for absent tags or warnings.
7. Use confidence between 0 and 1.
