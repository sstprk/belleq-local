# Local interface and optional hosting

## Recommended local demonstration

Use the full simulator from [its guide](../simulator/README.md) and open
http://127.0.0.1:8010. It records local runs and works offline after package
installation. It does not contact the minis and does not need model downloads.

The `web-demo/` directory is an optional self-contained hosting adapter. It copies
the same frozen inference engine and four model JSON files but does not train,
include the raw research archive or persist server-side runs. The publication
checker verifies that its model files match the simulator's files.

For the same hosted-style behavior locally, from the repository root:

```bash
simulator/.venv/bin/python web-demo/tools/preview.py --port 8011
```

Open http://127.0.0.1:8011. This version uses CSV/JSON downloads for retention,
not automatic server-side run storage. Stop with Ctrl+C.

## Optional Vercel deployment

Import this GitHub repository in Vercel and set **Root Directory to `web-demo`**.
Choose **Other** for the framework and leave the build command empty; the included
`vercel.json` sets the static output and Python API rewrites. There are no required
API keys or lab IP addresses for inference. Do not upload a macOS virtual
environment or change the root to the whole research archive.

The Python entry point is `web-demo/api/index.py`; NumPy is installed from the
adapter's pinned requirement. Static files are in `public/`. The paths are `/`,
`/health`, `/v1/model`, `/v1/simulate` and `/v1/predict`. Maximum HTTP draws are
20,000. The service never executes shell commands or accesses a live LLM.

After deployment, check `/health` and submit the default broadcast scenario.
Expect approximately 339 ms modeled retrieval and 18.6 kB modeled captured traffic,
not those values for the hosting request latency. Verify sharing/protection settings
before sending a URL to readers. A local preview passing is not a verified cloud
deployment; this publication does not require or claim a live Vercel URL.

Vercel runtime guidance is at
https://vercel.com/docs/functions/runtimes/python and configuration guidance at
https://vercel.com/docs/project-configuration. The original standalone adapter
instructions in `web-demo/` apply when that directory is uploaded as its own repo;
for this combined repository use the root-directory setting above.
