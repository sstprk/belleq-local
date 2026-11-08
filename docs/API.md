# HTTP API catalog

## Real laboratory service

Default coordinator: `http://192.168.50.11:8000`; workers: `.12`, `.13`, `.14` on
port 8000. Endpoints use HTTP JSON unless stated otherwise. If enabled, send the
shared `X-API-Key` header. The generated OpenAPI reference is at `/docs`.

| Method and path | Role | Result |
|---|---|---|
| `GET /health/live` | Any mini | Process liveness |
| `GET /health/ready` | Any mini | Dependency, model and collection readiness |
| `POST /v1/documents/text` | Any mini | Chunk/embed/upsert a JSON text document |
| `POST /v1/documents/upload` | Any mini | Multipart `file`: TXT, MD, PDF, DOCX or HTML |
| `POST /v1/retrieve/local` | Any mini | Search this mini only |
| `POST /query` | Any mini | Alias of local retrieval |
| `POST /v1/retrieve/aggregate` | Coordinator | Route/fan out, deduplicate and select global top-k |
| `POST /v1/answer` | Coordinator | Aggregate, inject context and generate a local answer |

An aggregate request is never sent to a worker aggregate endpoint. Even when
mini-1 is included in its worker list, the internal request is local retrieval.

### Upload and search

```bash
curl --fail http://192.168.50.12:8000/v1/documents/text \
  -H 'Content-Type: application/json' \
  -d '{"title":"Example","source":"example.txt","text":"Victor Frankenstein created a creature."}'
curl --fail http://192.168.50.12:8000/v1/documents/upload -F 'file=@example.txt'
curl --fail http://192.168.50.12:8000/v1/retrieve/local \
  -H 'Content-Type: application/json' \
  -d '{"query":"Who created the creature?","top_k":3}'
curl --fail http://192.168.50.11:8000/v1/retrieve/aggregate \
  -H 'Content-Type: application/json' \
  -d '{"query":"Who created the creature?","mode":"random_sequential","random_seed":42,"top_k":3,"per_node_k":5,"min_score":0.70}'
curl --fail http://192.168.50.11:8000/v1/answer \
  -H 'Content-Type: application/json' \
  -d '{"query":"Who created the creature?","mode":"broadcast","top_k":3,"per_node_k":5,"min_score":0.70}'
```

| Request field | Meaning |
|---|---|
| `query` | Nonempty question; at most 2,000 characters |
| `top_k` | Global context/result target; default 3 |
| `per_node_k` | Requested candidates per worker; set 5 for the recorded protocol |
| `mode` | `broadcast`, `semantic_sequential`, `random_sequential`; omitted uses config |
| `random_seed` | Seed for random worker order; default 0; runner varies it reproducibly |
| `min_score` | Similarity cutoff; use .70 for matched main comparisons |
| `allow_partial` | Default false; explicit opt-in to incomplete successful responses |
| `query_id` | Propagated identifier; generated when omitted |

Chunks expose text, chunk ID, document ID, source/title, index, score, canonical
content hash, fingerprint and locations. Worker records include status, candidate
metadata, request/response body bytes and timing. Routing records identify ranked,
visited and skipped workers and stopping reason. Answer responses add `answer`,
`context_chunks`, `generation_ms` and `end_to_end_ms`. Empty context returns the
service's no-context message with zero generation time.

### Failure semantics

- Bad inputs: 422.
- Failed worker, timeout or schema mismatch: aggregate 503 by default, with the
  available retrieval details in the error body.
- `allow_partial:true`: can return 200, but `partial:true` and failed node details
  remain. If all workers fail, it remains 503.
- Generation failure: 502 with the retrieved context preserved in `detail`.

Do not count a 200 partial response as a complete run. Body-byte counts are not
Ethernet traffic; failed request bytes indicate a prepared body, not confirmed
delivery. Timing and traffic definitions are in [the protocol](EXPERIMENTS.md).

## Simulator service

The independent local service binds to `http://127.0.0.1:8010` and does not forward
requests to the lab. `/` serves its static interface.

| Method and path | Input/output |
|---|---|
| `GET /health` | Simulator process/version |
| `GET /v1/model` | Model card and supported scope |
| `POST /v1/simulate` | Scenario JSON → distributions, evidence level, warnings, run ID |
| `POST /v1/predict` | `question`, `method` → native-setting point estimates |

```bash
curl --fail http://127.0.0.1:8010/v1/simulate \
  -H 'Content-Type: application/json' \
  -d '{"mode":"assumption","method":"semantic_sequential","nodes":8,"draws":1000,"threshold":0.7,"top_k":3,"semantic_owner_first_probability":0.57}'
```

`nodes` excludes the coordinator. Native empirical settings are fixed; trace
settings replay three recorded workers. Assumption mode is explicit and has no
predicted quality. Unsupported combinations give 422. The optional hosted
adapter has the same endpoint names, but its runs are download-only rather than
saved on the server; see [web hosting](WEB_DEMO.md).
