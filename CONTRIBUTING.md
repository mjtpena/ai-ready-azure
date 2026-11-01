# Contributing

This repository is the companion to a recorded course, so its demos must keep printing the numbers the video shows
(`docs/EXPECTED.md`). Before opening a pull request:

1. `python -m pytest tests -q` passes (data anchors, tool contracts, the scrub check).
2. `python scripts/scrub_check.py` reports zero hits. The course is built around a fictional operator; keep it that way.
3. Never commit `.env`, `.deploy-outputs.json`, evaluation results or recorded media.

Issues and pull requests that improve the Bicep, the agent definition or the evaluation harness are welcome. Changes
to the dataset need a matching update to `docs/EXPECTED.md` and the evaluation ground truths.
