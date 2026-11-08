# Research data and licensing

## Availability

The v0.2.0 release includes `belleq-research-data-v0.2.0.tar.gz`, approximately
23.3 MB compressed, containing **89 allowlisted research input files**. Its exact
URL, size and SHA-256 are in [data-release.json](../data-release.json). The source
checkout has everything needed for simulator inference without this download.

```bash
python3.12 scripts/fetch_research_data.py
# Or import an already downloaded file without internet:
python3.12 scripts/fetch_research_data.py --archive /path/to/belleq-research-data-v0.2.0.tar.gz
```

The fetcher verifies archive bytes before extraction, restricts member paths and
checks each input hash. A different preexisting input is not overwritten. Raw
files are ignored by Git after extraction. The release archive is part of this
software version; it is not a claim of a separately registered dataset DOI.

## Included inputs

| Location after extraction | Content |
|---|---|
| `simulator/data/raw/combined_070.csv` | 2,000 real query-policy attempts; four methods × 500 questions at .70 |
| `simulator/data/raw/oct12/responses.jsonl` | Original categorical semantic/broadcast responses and warmups |
| `simulator/data/raw/oct14/*/responses.jsonl` | Random-order and single-DB responses at .70 and auxiliary .80 |
| `simulator/data/raw/oct12/questions.generated.jsonl` | Same 500 synthetic questions, references and source evidence |
| `simulator/data/raw/oct12/chunks.jsonl` | Canonical chunks and hashes |
| `simulator/data/raw/oct12/books/` | Cleaned files used for upload |
| `simulator/data/raw/oct12/raw_books/` | Downloaded book originals with their notices |
| `simulator/data/raw/oct12/categorical.complete-records.pcap` | Original capture with incomplete trailing record removed |
| `simulator/data/raw/oct14/capture_restart.pcap` | Restarted matched-threshold capture |
| `simulator/data/raw/service_snapshot/` | Exact service source used in the recorded later runs |
| `simulator/data/source_manifest.json` | Public input sizes/hashes and original archived hashes |

The full private acquisition archive contained 132 files, as described in the
historical report. This public subset excludes personal provisioning scripts,
duplicate/incomplete captures and machine acquisition logs that are unnecessary
for analysis. The two selected PCAPs suffice for the documented 2,000-query byte
audit. The exact raw vectors/model weights are not included; the consolidated
copy audit and canonical source inputs are included.

## Publication transformation

In `combined_070.csv`, the `source_csv` field originally contained a personal
absolute path. Only that field was replaced with the filename. All other fields,
including measurements, question IDs, responses and labels, were retained.
The public and archived-original SHA-256 values are both recorded. CSV formatting
can differ after serialization, so the public file hash differs from the original
audit's input hash. The numeric model inputs and frozen model are unchanged.

The raw question/response files, selected packet captures and book files were
copied without modification. Importantly, a shortened path is not an additional
observation, a repaired result or a change to a failed trial.

## Dataset unit and fields

The main unit is one question under one policy. The same `case_id` appears once
per policy, with a distinct `sample_id`. There are 500 questions, not 2,000
independent configurations or hardware sessions. The two HTTP 503 rows remain.

| Group | Representative fields |
|---|---|
| Identity | `sample_id`, `case_id`, `run_id`, `experiment_method`, `scenario`, `placement`, `policy` |
| Question/answer | `question`, `answer`, `expected_answer`, `book_id`, `book_title`, `source_url` |
| Grounding | `evidence_quote`, `source_chunk_text`, `relevant_hashes_json`, `reviewed`, `quality_status` |
| Configuration | `min_score`, `top_k`, `per_node_k`, `concurrency`, `seed`, model/corpus hashes |
| Outcome | `complete`, `http_status`, `error`, failed-node and raw-response JSON |
| Application time | `router_ms`, `aggregate_ms`, `generation_ms`, `client_ms`, worker embedding/search/round-trip |
| Routing | ranked, visited and skipped nodes, routing seed, stopping reason |
| Traffic | worker body bytes, per-mini frame bytes/packets, ACK RTT and window Mbps |
| Derived analysis | `network_frame_bytes`, `body_bytes`, question-level `split` in processed output |

Large nested columns are JSON strings within CSV cells. Read with UTF-8 BOM
support (`utf-8-sig`) and a sufficiently large CSV field-size limit. Missing
latency or quality means unobserved, not a measured zero. `expected_node` can
change for consolidation; use `original_categorical_node` or the corpus manifest
when reasoning about original categorical placement.

## Quality labels and auxiliary data

Questions and reference answers are synthetic and quote verified, not human
reviewed. Labels mark particular source passages and are nonexhaustive. Hit@3
means a labeled chunk was retrieved, not that the generated answer is correct.
Missing the reference does not establish that every returned passage is irrelevant.
Legacy token-overlap heuristics are retained but are not primary accuracy claims.

The .80 random-order and single-DB runs have 500 attempts each. Each contains
23 reference hits (4.6%) and 470 no-context requests. They are not all misses, but
they are excluded from the main matched .70 comparison because the workload differs.
The 3,000 visit permutations in the normal clone are derived replay records,
not 3,000 independent physical experiments.

## Licenses and third-party materials

The repository's original software and research metadata are released under
[MIT](../LICENSE). Original book texts and quotations retain their own terms;
we do not claim them as newly MIT-licensed works. Source URLs are in the corpus
manifest and downloaded originals retain their Project Gutenberg notices.
Consult those notices and the source terms when redistributing the texts.

Ollama, Qdrant, Python packages and model weights are external dependencies with
their own licenses. This repository does not redistribute the Qwen or embedding
model weights or grant new rights over them. Method documentation snapshots are
not bundled as new MIT content; reference URLs are retained instead.
