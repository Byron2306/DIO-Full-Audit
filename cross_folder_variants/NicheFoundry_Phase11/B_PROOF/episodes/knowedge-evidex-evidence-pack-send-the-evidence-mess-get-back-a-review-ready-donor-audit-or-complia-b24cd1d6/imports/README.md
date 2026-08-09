# Imports

1. Build the episode once so manifests and folders exist.
2. Use `adobe_storyboard.html`, `adobe_brief.md`, and `adobe_export_list.csv` for the Adobe-first visual workflow.
3. Or use `canva_storyboard.html`, `canva_brief.md`, and `canva_export_list.csv` for the Canva workflow.
4. Use `elevenlabs_lines.csv` or `npm run generate:elevenlabs -- episodes/<episode-id>` for narration.
5. Put exported PNGs in `imports/canva/` and MP3s in `imports/elevenlabs/`.
6. Run `npm run render:episode -- episodes/<episode-id>` to render with imported assets.

Preferred PNG names are the short IDs like `Q1_question.png`.
