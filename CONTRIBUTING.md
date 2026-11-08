# Contributing

Open an issue describing the problem, expected behavior, operating system and
software versions. Include a minimal example without passwords, API keys or
private documents. Contributions are provided under the repository's MIT license.

Use Python 3.12. From the repository root:

```bash
uv sync --frozen
uv run --frozen pytest -q
python3 scripts/check_publication.py
```

For simulator changes, install its separate environment and follow
[testing](docs/TESTING.md). Preserve the held-out question split and distinguish
measurements, replay and assumption-based outputs. Do not train on derived
permutations as if they were independent observations.

New experiment data belong in a versioned release asset with checksums and an
acquisition description. Add a new dataset version rather than replacing the
benchmark to improve reported numbers. Report negative results as well.
Candidate filtering, deduplication and stopping changes need behavior tests.

Keep method colors and shapes consistent across figures. Update source CSVs and
captions with plotted results. Describe checks actually run; mocked tests are
not new Mac mini experiments.
