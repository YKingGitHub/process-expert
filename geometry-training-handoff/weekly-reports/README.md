# Weekly report publishing

GitHub Pages publishes this branch as an immutable ISO-week archive. The stable routes are:

- `/` — report archive and latest-week entry.
- `/latest/` — the newest registered report.
- `/reports/YYYY-Www/` — one permanent weekly report.

## Add a new week

Generate a self-contained HTML file at a new path; never reuse an older week's path:

```bash
geometry-training-handoff/weekly-reports/2026-W36/index.html
```

Register it. The helper computes and stores its SHA-256 and refuses to overwrite an existing week:

```bash
python geometry-training-handoff/weekly-reports/register_report.py \
  --week 2026-W36 \
  --date 2026-09-01 \
  --title '本周标题' \
  --summary '一句话摘要' \
  --source geometry-training-handoff/weekly-reports/2026-W36/index.html
```

Validate the complete archive before pushing:

```bash
python geometry-training-handoff/weekly-reports/build_site.py \
  --manifest geometry-training-handoff/weekly-reports/reports.json \
  --output /tmp/process-expert-weekly-pages
```

Push to `agent/group-meeting-webpage`. The `weekly-reports-pages.yml` workflow deploys the new archive automatically. Existing weeks remain in the manifest with fixed source paths and checksums; a changed historical source makes the build fail instead of replacing its deployed route.
