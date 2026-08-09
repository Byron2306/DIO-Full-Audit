# Sophia Blinded Visual Inspection Packet

Fill the CSV without looking at Gemini/native-vision outputs.

Columns:

- `human_visible_numbers`: semicolon-separated numbers exactly visible in the figure/chart/table, e.g. `16%;84.2`.
- `human_caption_summary`: brief description of what the caption or visual actually says.
- `human_uncertainty_flags`: use terms like `blurry`, `cropped`, `caption_conflict`, `table_unclear`, or `none`.
- `human_verdict`: one of `supports_native`, `supports_ocr`, `conflict`, `unclear`, `not_visual`.
- `rater_id`: stable rater code.

After completion, rerun the benchmark with `--human-inspection-csv path/to/this.csv`.
