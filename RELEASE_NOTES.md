# v0.2.0 research software and data release

Belleq Local now includes the actual application-level distributed retrieval
service, the calibrated simulator, English local web UI, optional stateless
hosting adapter and detailed installation/reproduction instructions.

The reference experiment contains 2,000 main attempts with 500 shared questions
across semantic sequential, broadcast, random sequential and consolidated
single-database policies. Two errors are retained. Random sequential changes
worker order on categorical data; it is not random chunk placement. Additional
.80 runs remain auxiliary. New worker-count outputs are explicit assumptions.

## Assets

- `belleq-research-data-v0.2.0.tar.gz`: 89 public inputs, including the main CSV,
  raw responses, questions, books with original notices, canonical chunks,
  selected PCAPs and the exact recorded service source.
- `belleq-paper-report-v0.2.0.zip`: report PDF/DOCX, five PNG/PDF figures and
  extracted numerical tables, including the 2026-10-23 visual revision.
- `SHA256SUMS`: checksums for both assets. The data fetcher also verifies the
  archive using the hash committed in `data-release.json`.

Only personal `source_csv` paths are shortened in the public data; numeric
observations are unchanged. The frozen model is not retrained for publication.
The release includes software licensing and citation metadata but does not
claim a journal publication, DOI registration or new hardware experiment.

See README and docs for the actual testing scope. Use this tag and commit for
journal code availability; archive it with a DOI service separately if required.
