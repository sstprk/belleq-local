# Source and artifact provenance

The lab service derives from the author's Belleq work, originally inspected at
`https://github.com/Salih-Toprak/belleq-user.git`, commit
`1fcd009dadd54eec3531f8ce9fee29022fb6d9fa`.

The original `app/ingestion/chunker.py` and `app/ingestion/extractors.py` were copied
as `belleq_lab/chunker.py` and `belleq_lab/extractors.py`. Ollama embedding, Qdrant
upsert/query and retrieval API patterns were adapted from the original pipeline.
The independent FastAPI service, schema checks, HTTP aggregation, routing,
evaluation and simulator were developed for the lab experiment.

The existing public repository baseline is commit
`a66cba4e111cb44f7e13428ddbf6bd287aacf5a0`. The lab source in this publication starts
from the exact later service snapshot archived with the 2026-10-14 experiment;
it includes the recorded random sequential extension. The source snapshot is
also retained unchanged in the checksummed data release.

The frozen simulator model and figures come from the 2026-10-20 research project
and its 2026-10-23 visual revision. Public assembly on 2026-11-08 does not retrain
the published model or add physical observations. New publication tools and docs
are separately described in [the changelog](CHANGELOG.md).

[Imported-file hashes](provenance/imported_files.json) record the initial copy
before publication-specific edits. [Publication validation](provenance/publication_validation.json)
records subsequent checks. Source labels are portable archive-relative descriptions,
not machine usernames or absolute home paths.

The source owner authorized republication under MIT on 2026-11-08. Earlier local
notes deliberately deferred this decision; those historical notes are retained
under `docs/legacy/` and are not the current license statement. The current
[LICENSE](LICENSE) governs the original software. External texts, dependencies
and model weights retain their own terms, described in [data licensing](docs/DATA.md).
