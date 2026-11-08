# Experiment protocol

This guide runs new physical measurements. To regenerate the existing paper
analysis instead, use [reproducibility](REPRODUCIBILITY.md). New execution will
not reproduce historical wall-clock durations exactly.

## Corpus and categorical placement

Fetch the research archive on the management machine while internet is available:

```bash
python3.12 scripts/fetch_research_data.py
```

Cleaned upload files are under `simulator/data/raw/oct12/books/`; downloaded
originals, including their notices, are under `raw_books/`. They have different
hashes. The public `config/categorical/corpus.json` preserves both the original
download hash and the cleaned `upload_sha256`, expected document ID and chunk count.

| Worker | Category | Books | Chunks |
|---|---|---|---:|
| mini-2 | Gothic/speculative | Frankenstein; Dracula; Dr Jekyll and Mr Hyde; The Time Machine | 4,529 |
| mini-3 | Detective | The Hound of the Baskervilles; The Adventures of Sherlock Holmes; A Study in Scarlet; The Sign of the Four | 3,998 |
| mini-4 | Social/romance | Persuasion; Pride and Prejudice; Emma; Sense and Sensibility | 7,894 |

The partitions are categorical, not balanced by chunk count. Install the categorical
configs on all four minis as described in [lab setup](LAB_SETUP.md). Use a new
collection for each placement experiment; change its name consistently in all
configs before starting services. Do not mix new and old corpus versions.

From the management computer with the root lab environment installed:

```bash
.venv/bin/python scripts/ingest_categorical.py > ingestion-categorical.jsonl
```

This uploads the checked files to their assigned worker APIs and verifies returned
document IDs and chunk counts. It does not download books during measurement.
It fails on a file-hash mismatch or a failed ingestion. Partial batches can remain
after failure; same-document retries use deterministic IDs, but changed documents
need a new collection rather than silently accumulating old versions.

The reference tokenizer is not used for chunking: it is approximately 512
characters with 64-character overlap and sentence-boundary adjustment. Record
the actual 16,421 chunk count; do not describe these as 512-token chunks.

## Main policy comparison

Use the same 500 questions in `simulator/data/raw/oct12/questions.generated.jsonl`.
Their qrels are unreviewed synthetic references, so explicitly use `--allow-draft`.
Run the evaluator on mini-1, with capture on mini-1, for same-clock query windows.

```bash
# From the repository root on mini-1. Each run needs a fresh output directory.
.venv/bin/python scripts/evaluate.py \
  --scenario categorical --mode semantic_sequential \
  --url http://192.168.50.11:8000/v1/answer \
  --queries simulator/data/raw/oct12/questions.generated.jsonl \
  --top-k 3 --per-node-k 5 --min-score 0.70 \
  --warmup 0 --repeat 1 --seed 20261012 --allow-draft \
  --output results/categorical-semantic-01
```

This yields 500 measured attempts, including failures, rather than retrying failed
queries until they disappear. For retrieval without answer generation, use the
`/v1/retrieve/aggregate` URL. The evaluator's `--warmup` counts complete passes over
the set; the example uses zero and assumes a separately recorded preflight. It
does not imitate the original ad hoc three-query warmup. Separate warmup rows from
measurement rows whenever warmup passes are enabled.

Run broadcast with `--mode broadcast` and a new output directory. Run the categorical
random-order condition with `--scenario random_node_order --mode random_sequential`.
The evaluator sends a reproducible per-attempt routing seed. Reusing one fixed
`random_seed` directly in curl would reuse an order, not vary it between questions.

The output directory contains:

- `manifest.json`: endpoint, settings, query-file SHA-256 and judgment status.
- `raw.jsonl`: each request, response/error, query ID and timing window.
- `queries.csv`: question, expected answer, generated answer where applicable,
  quality metrics, timing, routing seed and nested result fields as JSON cells.
- `nodes.csv`: per-query worker status, body bytes, timing and observable quality.
- `summary.json`: all-attempt completion/hit counts and complete-only summaries.

The JSON cells retain additional fields for later analysis. A skipped worker has
not been measured and is not treated as a retrieval miss or zero latency.

## Consolidated single-database baseline

Keep the categorical stores intact. On mini-2, start a second Qdrant instance and
its retrieval API; it uses a separate volume, Qdrant port 6335 and API port 8001:

```bash
docker-compose -f compose.single-db.yaml up -d
BELLEQ_CONFIG=config/categorical/single-worker.json .venv/bin/python -m belleq_lab
```

Start this API before copying points so it creates the destination collection's
embedding schema. In separate terminals on the management computer establish
SSH forwards; replace `LABUSER` on each machine:

```bash
ssh -N -L 16332:127.0.0.1:6333 -L 16335:127.0.0.1:6335 LABUSER@192.168.50.12
ssh -N -L 16333:127.0.0.1:6333 LABUSER@192.168.50.13
ssh -N -L 16334:127.0.0.1:6333 LABUSER@192.168.50.14
```

Then, from the management computer:

```bash
.venv/bin/python scripts/consolidate.py \
  --sources http://127.0.0.1:16332 http://127.0.0.1:16333 http://127.0.0.1:16334 \
  --destination http://127.0.0.1:16335 --collection lab_categorical_v1 \
  --output results/consolidation-01.json
```

This refuses a nonempty destination, checks fingerprints, copies stored vectors
and payloads without re-embedding and verifies the copied payloads and components.
Close the forwards before capture. On mini-1 start the alternate coordinator:

```bash
BELLEQ_CONFIG=config/categorical/single-coordinator.json .venv/bin/python -m belleq_lab
```

Its API is port 8003 and its only worker is mini-2:8001. Evaluate with
`--scenario single_db --mode broadcast --nodes mini-2` and
`--url http://192.168.50.11:8003/v1/answer`. The collection name must match the
categorical source in all example configs. If a copy fails partway, archive the
failure and use a new empty destination; the script does not delete or repair it.

## Network capture

Finish downloads, ingestion, initialization and model checks, then isolate every
mini as described in [setup](LAB_SETUP.md). Keep the capture terminal separate from
the evaluator. On mini-1, first verify the Ethernet interface:

```bash
route -n get 192.168.50.12
mkdir -p results/captures
sudo tcpdump -i en0 -n -s 0 -U \
  -w results/captures/categorical-01.pcap \
  'host 192.168.50.11 and (tcp port 8000 or tcp port 8001)'
```

Replace `en0` if necessary. Start capture before the evaluator. After the run,
Ctrl+C tcpdump and retain its captured/received/kernel-dropped counts. Do not
accept a partial trailing PCAP record silently. Captures and evaluator must use
the same host clock for matching query windows.

```bash
.venv/bin/python scripts/network_report.py \
  --pcap results/captures/categorical-01.pcap \
  --run results/categorical-semantic-01 \
  --ports 8000 8001 --output results/network-categorical-01
```

The coordinator capture observes both directions of coordinator-worker traffic
and can attribute it to worker IPs. Do not sum all endpoints' TX+RX to estimate
unique traffic: each packet then appears at both ends. Additional per-mini captures
are useful for diagnosis, but should be analyzed separately.

| Metric | Meaning and boundary |
|---|---|
| `embedding_ms` | Worker-local query embedding, including configured model-load behavior |
| `search_ms` | Qdrant vector search; distinct from embedding and transport |
| `round_trip_ms` | Coordinator-observed worker call duration |
| `aggregate_ms` | Router, worker queries and merge, excluding answer generation |
| `generation_ms` | Local answer-model call; model loading may be included |
| `client_ms` | Full evaluator request duration |
| HTTP body bytes | Application payload sizes, not TCP/Ethernet totals |
| Captured frame bytes | Ethernet capture frame accounting inside selected windows; excludes physical overhead |
| TCP ACK RTT | Transport estimate influenced by host ACK behavior; not one-way latency |
| HTTP response time | Transport plus server work, distinct from pure network delay |
| Window Mbps | Captured bytes divided by query-window duration; not capacity or maximum throughput |

No claim of cold OS/Qdrant caches is made. Ollama `keep_alive:0` unloads models
after calls in the archived service, so its costs must not be compared as if they
were only vector-search or network latency.

## Fair comparisons and extensions

Keep corpus, questions, models/digests, candidate counts, threshold and concurrency
fixed when comparing policies. Use independent sessions and randomized policy
order for a stronger study. Record errors and no-context outcomes. Do not select
only successful questions after seeing results. The original sessions were not a
fully randomized crossover experiment, and this limitation remains in the report.

`scripts/experiment.py` can generate 1/2/3-worker configs with fresh collection
names; `scripts/partition.py` partitions whole documents. It does **not** provide
random chunk placement or guarantee equal chunk counts. Changing placement must
be a separate experiment with preserved canonical IDs, not a relabeling of
`random_sequential`. Larger corpora, concurrency, worker-count scaling, queues and
WAN behavior need new measurements before a predictive claim is made.
