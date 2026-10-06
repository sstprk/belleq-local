import asyncio
import json
import logging
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from typing import Literal
from .routing import rank_nodes
import httpx
from fastapi import FastAPI, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from .config import load_settings
from .backends import Backends
from .chunker import content_hash
from .extractors import extract_text, ExtractionError

log = logging.getLogger('belleq.metrics')

class Query(BaseModel):
    query: str = Field(min_length=1, max_length=2000, pattern=r'\S')
    top_k: int = Field(default=3, ge=1, le=100)
    per_node_k: int | None = Field(default=None, ge=1, le=200)
    mode: Literal["broadcast", "semantic_sequential"] | None = None
    min_score: float | None = Field(default=None, ge=-1, le=1, allow_inf_nan=False)
    allow_partial: bool = False
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()), max_length=64)

class TextDocument(BaseModel):
    text: str = Field(min_length=1, max_length=2_000_000)
    title: str = Field(default='document', max_length=500)
    source: str = Field(default='upload', max_length=1000)


def merge_results(results, top_k):
    unique = {}
    for node_id, hits in results:
        for hit in hits:
            key = content_hash(hit['text'])
            location = {'node_id': node_id, 'doc_id': hit['doc_id'],
                        'chunk_id': hit['id'], 'source': hit['source']}
            if key not in unique:
                unique[key] = {**hit, 'locations': [location]}
            else:
                old = unique[key]
                locations = old['locations'] + [location]
                if hit['score'] > old['score']:
                    unique[key] = {**hit, 'locations': locations}
                else:
                    old['locations'] = locations
    return sorted(unique.values(), key=lambda h: (-h['score'], str(h['id'])))[:top_k]


def create_app(settings=None, backend=None, node_client=None):
    s = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(trust_env=False) as client:
            app.state.backend = backend or Backends(s, client)
            app.state.nodes = node_client or client
            app.state.catalogue = None
            app.state.catalogue_lock = asyncio.Lock()
            await app.state.backend.initialize()
            yield

    app = FastAPI(title='Belleq Lab', lifespan=lifespan)

    @app.middleware('http')
    async def access(request: Request, call_next):
        if s.api_key and not secrets.compare_digest(request.headers.get('x-api-key', ''), s.api_key):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=401, content={'detail': 'Invalid API key'})
        return await call_next(request)

    @app.get('/health/live')
    async def live():
        return {'status': 'ok', 'node_id': s.node_id}

    @app.get('/health/ready')
    async def ready():
        b = app.state.backend
        try:
            await b.request('GET', s.qdrant_url, '/collections/' + s.collection)
            tags = await b.request('GET', s.ollama_url, '/api/tags')
            if not any(m['name'] == s.embedding_model and m['digest'] == b.signature['digest']
                       for m in tags['models']):
                raise ValueError('Embedding model changed or absent')
        except Exception as exc:
            raise HTTPException(503, 'Dependency unavailable or embedding changed') from exc
        return {'status': 'ready', 'node_id': s.node_id, 'collection': s.collection,
                'signature': b.signature, 'fingerprint': b.fingerprint}

    async def ingest(text, title, source):
        started = time.perf_counter()
        try:
            result = await app.state.backend.ingest(text, title, source)
        except Exception as exc:
            log.exception('ingestion_failed')
            raise HTTPException(502, 'Ingestion failed; retry is idempotent but prior batches may remain') from exc
        return {**result, 'node_id': s.node_id, 'total_ms': (time.perf_counter()-started)*1000}

    @app.post('/v1/documents/text')
    async def text_document(doc: TextDocument):
        return await ingest(doc.text, doc.title, doc.source)

    @app.post('/v1/documents/upload')
    async def upload(file: UploadFile):
        raw = await file.read(s.max_upload_bytes + 1)
        await file.close()
        if len(raw) > s.max_upload_bytes:
            raise HTTPException(413, 'Upload too large')
        try:
            text = await asyncio.to_thread(extract_text, raw, file.filename or 'document.txt', file.content_type or '')
        except ExtractionError as exc:
            raise HTTPException(422, str(exc)) from exc
        if not text.strip():
            raise HTTPException(422, 'Document has no text; scanned PDF requires external OCR')
        return await ingest(text, file.filename or 'document', file.filename or 'upload')

    @app.post('/query')  # compatible query/top_k input, expanded scored chunk output
    @app.post('/v1/retrieve/local')
    async def local(q: Query):
        b = app.state.backend
        t = time.perf_counter()
        try:
            await ready()  # detect on-disk model replacement, not merely matching tag names
            checked = time.perf_counter()
            vectors = await b.embed([q.query], query=True)
            embedded = time.perf_counter()
            hits = await b.search(vectors[0], q.top_k)
        except HTTPException:
            raise
        except Exception as exc:
            log.exception('retrieval_failed query_id=%s', q.query_id)
            raise HTTPException(502, 'Local retrieval dependency failed') from exc
        end = time.perf_counter()
        result = {'query_id': q.query_id, 'node_id': s.node_id, 'chunks': hits,
                  'fingerprint': b.fingerprint, 'signature': b.signature,
                  'timings': {'readiness_ms': (checked-t)*1000,
                              'embedding_ms': (embedded-checked)*1000,
                              'search_ms': (end-embedded)*1000, 'total_ms': (end-t)*1000}}
        log.info(json.dumps({'event': 'local', 'query_id': q.query_id, 'node_id': s.node_id,
                             'timings': result['timings']}))
        return result

    async def aggregate(q):
        if not s.coordinator:
            raise HTTPException(403, 'Aggregator is disabled on this worker')
        started = time.perf_counter()
        mode = q.mode or s.retrieval_mode
        threshold = q.min_score if q.min_score is not None else (
            s.relevance_threshold if mode == 'semantic_sequential' else None)
        per_k = q.per_node_k or (max(5, q.top_k) if mode == 'semantic_sequential' else q.top_k)
        ranking = []
        router_ms = 0.0
        catalogue_ms = 0.0
        query_embedding_ms = 0.0
        catalogue_built = False
        ordered_nodes = s.nodes
        if mode == 'semantic_sequential':
            if any(not n.description.strip() for n in s.nodes):
                raise HTTPException(422, 'Semantic routing requires a description for every node')
            router_started = time.perf_counter()
            await ready()
            try:
                # Metadata embeddings only: local cached catalogue, never retrieval results.
                async with app.state.catalogue_lock:
                    if app.state.catalogue is None:
                        t = time.perf_counter()
                        vectors = await app.state.backend.embed([n.description for n in s.nodes])
                        # Validate before caching; also prevents retry with corrupt vectors.
                        rank_nodes(s.nodes, vectors[0], vectors)
                        app.state.catalogue = vectors
                        catalogue_ms = (time.perf_counter()-t)*1000
                        catalogue_built = True
                t = time.perf_counter()
                vector = (await app.state.backend.embed([q.query], query=True))[0]
                query_embedding_ms = (time.perf_counter()-t)*1000
                ranked = rank_nodes(s.nodes, vector, app.state.catalogue)
            except Exception as exc:
                log.exception('routing_failed query_id=%s', q.query_id)
                raise HTTPException(502, 'Semantic routing failed; no worker queried') from exc
            ordered_nodes = [n for n, score in ranked]
            ranking = [{'node_id': n.id, 'routing_score': score} for n, score in ranked]
            router_ms = (time.perf_counter()-router_started)*1000
        if per_k < q.top_k:
            raise HTTPException(422, 'per_node_k must be at least top_k')
        payload = json.dumps({'query': q.query, 'top_k': per_k, 'query_id': q.query_id},
                             ensure_ascii=False).encode()

        async def fetch(node):
            t = time.perf_counter()
            item = {'node_id': node.id, 'status': 'error', 'request_body_bytes': len(payload),
                    'response_body_bytes': 0}
            try:
                async with asyncio.timeout(s.node_timeout):
                    r = await app.state.nodes.post(node.url.rstrip('/') + '/v1/retrieve/local',
                        content=payload, headers={'content-type': 'application/json', 'x-api-key': s.api_key},
                        timeout=s.node_timeout)
                    item['response_body_bytes'] = len(r.content)
                    r.raise_for_status()
                    data = r.json()
                    if data['node_id'] != node.id or data['query_id'] != q.query_id:
                        raise ValueError('Node identity or query identity mismatch')
                    if data['fingerprint'] != app.state.backend.fingerprint or data['signature'] != app.state.backend.signature:
                        raise ValueError('Embedding schema mismatch')
                    # Validate remote hit shape before accepting the node as successful.
                    if len(data['chunks']) > per_k:
                        raise ValueError('Worker exceeded requested top_k')
                    for h in data['chunks']:
                        if not isinstance(h['text'], str) or not isinstance(h['score'], (float, int)):
                            raise ValueError('Invalid hit')
                        import math
                        if not math.isfinite(h['score']):
                            raise ValueError('Non-finite score')
                        for key in ('id', 'doc_id', 'source'):
                            if not isinstance(h[key], str):
                                raise ValueError('Invalid hit identity')
                    accepted = [h for h in data['chunks'] if h['text'].strip()
                                and (threshold is None or h['score'] >= threshold)]
                    item.update(status='ok', timings=data['timings'],
                                returned_chunks=len(data['chunks']), accepted_chunks=len(accepted))
                    return item, accepted
            except (TimeoutError, httpx.TimeoutException):
                item['error'] = 'timeout'
            except Exception as exc:
                item['error'] = str(exc) or type(exc).__name__
            finally:
                item['round_trip_ms'] = (time.perf_counter()-t)*1000
            return item, []

        search_started = time.perf_counter()
        if mode == 'broadcast':
            pairs = await asyncio.gather(*(fetch(n) for n in ordered_nodes))
        else:
            pairs = []
            for node in ordered_nodes:
                pairs.append(await fetch(node))
                accepted = merge_results([(n['node_id'], h) for n, h in pairs
                                          if n['status'] == 'ok'], q.top_k)
                # No speculative or background calls to remaining nodes.
                if len(accepted) >= q.top_k:
                    break
        received = time.perf_counter()
        statuses = [p[0] for p in pairs]
        failed = [n['node_id'] for n in statuses if n['status'] != 'ok']
        hits = merge_results([(n['node_id'], h) for n, h in pairs if n['status'] == 'ok'], q.top_k)
        visited = {n['node_id'] for n in statuses}
        target_reached = len(hits) >= q.top_k
        result = {'query_id': q.query_id, 'partial': bool(failed),
                  'routing': {'mode': mode, 'ranking': ranking,
                              'visited_nodes': [n['node_id'] for n in statuses],
                              'skipped_nodes': [n.id for n in ordered_nodes if n.id not in visited],
                              'min_score': threshold, 'target_chunks': q.top_k,
                              'target_reached': target_reached,
                              'stop_reason': ('target_reached' if mode == 'semantic_sequential'
                                              and target_reached else 'all_nodes_visited'),
                              'catalogue_built': catalogue_built}, 'failed_nodes': failed,
                  'nodes': statuses, 'chunks': hits, 'fingerprint': app.state.backend.fingerprint,
                  'timings': {'router_ms': router_ms, 'catalogue_embedding_ms': catalogue_ms,
                              'router_query_embedding_ms': query_embedding_ms,
                              'fanout_ms': (received-search_started)*1000,
                              'merge_ms': (time.perf_counter()-received)*1000,
                              'aggregate_ms': (time.perf_counter()-started)*1000},
                  'traffic': {'unit': 'application_http_body_bytes_not_ethernet',
                              'request_bytes': sum(n['request_body_bytes'] for n in statuses),
                              'response_bytes': sum(n['response_body_bytes'] for n in statuses)}}
        log.info(json.dumps({'event': 'aggregate', **{k: v for k, v in result.items() if k != 'chunks'}}))
        if failed and (not q.allow_partial or len(failed) == len(statuses)):
            raise HTTPException(503, result)
        return result

    @app.post('/v1/retrieve/aggregate')
    async def aggregate_endpoint(q: Query):
        return await aggregate(q)

    @app.post('/v1/answer')
    async def answer(q: Query):
        started = time.perf_counter()
        result = await aggregate(q)
        selected, blocks, used = [], [], 0
        for h in result['chunks']:
            # Whole chunks only; return exactly what went into the prompt.
            block = f"[{len(selected)+1}] {h['text']}"
            if used + len(block) + 2 > s.context_chars:
                continue
            blocks.append(block)
            selected.append(h)
            used += len(block) + 2
        result['context_chunks'] = selected
        if not selected:
            result.update(answer='İlgili bilgi bulunamadı.', generation_ms=0.0)
        else:
            t = time.perf_counter()
            try:
                data = await app.state.backend.generate(q.query, '\n\n'.join(blocks))
                result['answer'] = data['message']['content']
            except Exception as exc:
                raise HTTPException(502, {'message': 'Generation failed', 'retrieval': result}) from exc
            result['generation_ms'] = (time.perf_counter()-t)*1000
        result['end_to_end_ms'] = (time.perf_counter()-started)*1000
        log.info(json.dumps({'event': 'answer', 'query_id': q.query_id,
                             'generation_ms': result['generation_ms'],
                             'end_to_end_ms': result['end_to_end_ms']}))
        return result
    return app
