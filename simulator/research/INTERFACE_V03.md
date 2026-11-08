# Interface revision v0.3 — 20 October 2026

Requested changes: English interface, no Belleq branding in the interface, and clearer guidance for users who do not already know distributed retrieval terminology.

## Changes

- Neutral page title and header: **Search Simulator**. Brand mark removed. Downloaded files use `search-simulation` names.
- Plain-language setup choices: use the tested setup, try different match settings, or explore a different setup.
- Search strategy descriptions explain parallel and one-at-a-time behavior instead of requiring users to know “semantic routing” or “broadcast.”
- “Search computers” replaces “nodes”; the separate coordinating computer is explained.
- Match strictness is explicitly a similarity score, not answer accuracy.
- Optional controls explain passage count, repetitions, randomness seed, processing-time assumptions, and network settings.
- Results explain average waiting time, transferred data, the time for 95% of searches, and mean computers contacted.
- A short generated sentence interprets the result without introducing a new model prediction.
- More details includes definitions of average, median, p95, passages and units.
- Spreadsheet-friendly one-row CSV download added; full technical JSON retained. Automatic research run recording continues.
- All custom validation messages are English. Invalid optional fields reveal their containing panel before focusing the input.
- English QUICK_START.md added. Research history and raw inputs retain their original names and provenance.

## Verification

The current model artifacts match the v0.2 snapshot byte for byte. Calibration, learned regressions, uncertainty interpretation and original validation results are unchanged.

The browser was used to check native parallel, single-database with AI-writing time, eight-computer assumed semantic routing, and .80 threshold replay. Invalid computer count guidance was checked. The CSV was downloaded and parsed; values agree with the engine. The final page title is Search Simulator, its document language is en, and no old branding appears in visible page text.

Evidence: `results/ui_validation/v03/checks.json` and `results/ui_validation/v03/search-simulator-en.png`. Automated results remain in `results/verification.json`.
