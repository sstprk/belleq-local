# Testing and validation

Use Python 3.12. Unit tests do not require physical minis, Ollama or a running
Qdrant server. A passing mocked service test is not a new hardware measurement.

## Lab service and tools

From the repository root:

```bash
uv sync --frozen
uv run --frozen pytest -q
python3.12 scripts/check_publication.py
```

The test discovery scope is `tests/`, excluding archived service snapshots and
the separately installed simulator. Tests cover merge/deduplication, timeout and
partial failures, schema mismatches, prompt context, semantic routing, seeded
random routing, evaluation denominators, packet directions and consolidation
refusal conditions. The publication runner also preserves question/answer and
worker records and gives each attempt a recorded routing seed.

## Simulator

From `simulator/`, after installing its requirements:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

The 13 tests check replay semantics, distinct chunks before early stopping,
inclusive thresholds, Ridge objective/intercept behavior, grouped split integrity,
seeded joint sampling, generation toggle, invalid inputs and explicit assumption
scope. The saved replay table is historical evidence, not a substitute for a
new experiment.

With the research inputs downloaded, the more complete check is:

```bash
PYTHONPATH=src .venv/bin/python scripts/verify.py
```

It additionally verifies the 89 public input hashes and exercises the local web
server, static resource boundaries, native/assumption requests, recording and
invalid-setting responses. It writes a new `results/verification.json` and a
journal event. Thus, it needs permission to open localhost sockets and write outputs.

## Optional hosted adapter

Use the simulator environment, which already includes NumPy:

```bash
# From repository root:
simulator/.venv/bin/python web-demo/tools/check.py
simulator/.venv/bin/python web-demo/tools/preview.py --port 8011
```

The checker sends real local HTTP requests through the Python entry point,
including rewritten API paths, invalid inputs and every evidence mode. It does
not prove a Vercel deployment has succeeded. That requires testing the deployed
URL after publication. No cloud deployment is required for this repository.

## CI and actual run records

[GitHub Actions](../.github/workflows/ci.yml) runs lab tests and simulator checks
in separate jobs on Python 3.12. Actions are pinned to commit IDs. Runtime package
versions come from the lab uv lock and the simulator requirements lock; they are
intentionally separate environments.

The publication check record is in
[publication validation](../provenance/publication_validation.json). It lists the
checks actually completed when assembling this release, including fresh local
installation and analysis regeneration. It does not claim that the newly
parameterized tooling has been rerun on the original four physical minis.
