# Search Simulator

The English local interface, CLI and empirical model require no lab access.
The interface is v0.3.0; the frozen calibrated model is v0.1.0. This is a source
checkout application, not a standalone wheel containing all research files.

## Install and start

From this directory, use Python 3.12:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
PYTHONPATH=src .venv/bin/python -m belleq_sim serve --port 8010
```

Open http://127.0.0.1:8010. Leave the terminal open; Ctrl+C stops it. On macOS,
`./start.command` performs subsequent starts after installation. Set `PYTHONPATH`
to `src` in your shell when issuing commands without the prefix shown above.
The UI and its assets are local; no CDN, cloud model or authentication is used.

## Try reproducible scenarios

```bash
PYTHONPATH=src .venv/bin/python -m belleq_sim simulate \
  --config configs/empirical_broadcast.json --output results/example-broadcast
PYTHONPATH=src .venv/bin/python -m belleq_sim simulate \
  --config configs/assumption_8_workers.json --output results/example-eight
PYTHONPATH=src .venv/bin/python -m belleq_sim predict \
  --method broadcast --question 'What did Holmes discover?'
```

Use new output paths: the CLI refuses to overwrite a run directory. CLI exports
`summary.json` and `samples.csv`. The local HTTP server also saves runs under
`results/ui_runs/`. These are simulations and remain separate from real data.

| Mode | Valid scope |
|---|---|
| `empirical` | Threshold .70, top-k 3, per-worker-k 5; 3 workers for distributed policies, 1 for single DB. Joint resampling of measured records. |
| `trace` | Three categorical workers; change threshold/top-k on recorded candidate lists. No new ANN search or generated answers. |
| `assumption` | 1–64 virtual workers with reused cost/payload archetypes. Explicit semantic owner-first probability required for semantic routing. No quality prediction. |

The coordinator is excluded from `nodes`. `draws` is simulated repetitions, not
new experiments; HTTP supports up to 20,000 and CLI up to 100,000. Generation
toggle includes recorded writing durations, not new text generation. Service-time
multipliers and link penalties are assumptions, not learned hardware coefficients.

## HTTP examples

```bash
curl --fail http://127.0.0.1:8010/health
curl --fail http://127.0.0.1:8010/v1/model
curl --fail http://127.0.0.1:8010/v1/simulate \
  -H 'Content-Type: application/json' \
  -d '{"method":"broadcast","mode":"empirical","nodes":3,"draws":10000,"seed":20261020}'
curl --fail http://127.0.0.1:8010/v1/predict \
  -H 'Content-Type: application/json' \
  -d '{"method":"broadcast","question":"What did Holmes discover?"}'
```

Unsupported combinations return 422 rather than pretending to be validated.
The summary HTTP response omits per-draw samples; download exports or use the CLI.
The full API is in [the catalog](../docs/API.md).

## Model validation and limits

The question-disjoint split is 300 training, 100 validation and 100 held-out test
questions. Deployed artifacts use the first 400 questions and exclude all test
derivatives. Monte Carlo estimates distributions; Ridge is only a weak baseline.
The point predictor selected method means for retrieval and traffic. Client-time
Ridge has test R² around .025, so it is not a strong individual-query predictor.

The simulator does not model new corpus sizes, heterogeneous hardware, queues,
capacity, WAN congestion or real random chunk placement. [Results](../docs/RESULTS.md)
and [reproduction steps](../docs/REPRODUCIBILITY.md) explain the evidence levels.

## Offline use and tests

After installing dependencies, the bundled model and UI work offline. To prepare
installation on a disconnected computer, download platform-appropriate wheels
beforehand; macOS wheels cannot be reused on Linux.

```bash
.venv/bin/python -m pip download -r requirements.lock -d wheelhouse
# Later, on the same platform and Python version:
.venv/bin/python -m pip install --no-index --find-links wheelhouse -r requirements.lock
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Raw research inputs are needed for training and the full source-integrity check,
but not for inference or these unit tests. Fetch them from the repository root
using `python3.12 scripts/fetch_research_data.py`. Do not copy `.venv` between machines.
