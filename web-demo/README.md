# Search Simulator — Vercel demo

This is the small deployable demo, not the full research archive. It includes the English interface, the inference engine, and four JSON model files. It does not include raw experiments, books, packet captures, training scripts, offline wheels, or a Python virtual environment.

## Deploy from GitHub

1. Create a GitHub repository. A private repository works with the Vercel GitHub integration.
2. Upload **the contents of this folder**, with `vercel.json` at the repository root.
3. In Vercel, select **Add New → Project**, import the repository and choose **Other** as the framework preset.
4. Keep the root directory at the repository root (`./`). Do not enter a build command. The included configuration sets the static output to `public` and connects the Python API automatically.
5. Deploy. No API keys, Qdrant, Ollama, or environment variables are needed.

Open the deployment URL and check `/health`. Then estimate the default scenario: approximately **339 ms**, **18.6 kB per search**, and **3 computers contacted**, using the bundled model and default seed.

The Python function is in `api/index.py`. Vercel installs `numpy==2.3.5` for its own Linux/Python environment; do not upload macOS `.venv` files or offline wheel packages.

## Hosting behavior

- `/`: static interface from `public/`.
- `/v1/simulate`: Python simulation endpoint.
- `/v1/predict`: point prediction for the native tested configuration.
- `/v1/model`: model metadata and limitations.
- `/health`: deployment health.

The hosted demo returns summaries and lets visitors download CSV/JSON results. It **does not permanently save runs on the server**. The full local research version still retains its automatic run recording.

This is a simulation, not a live connection to the lab. Additional computer counts are assumption scenarios, not validated scaling results. Model artifacts are copied unchanged from the local research project. Hosting response time is not the modeled retrieval time shown in results.

## Local checks

Install the one runtime dependency into a Python 3.12 environment:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python tools/check.py
.venv/bin/python tools/preview.py --port 8011
```

The preview server tests the Python handler and serves the same interface locally. A local preview does not replace checking a real Vercel deployment. No Vercel deployment has been performed as part of preparing this folder.

## Official references

- [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python)
- [Vercel project configuration](https://vercel.com/docs/project-configuration)
- [GitHub integration](https://vercel.com/docs/git/vercel-for-github)
