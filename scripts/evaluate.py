"""Reproducible retrieval-only experiment; no extra local probes during the run."""
import argparse
import asyncio
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from belleq_lab.evaluation import quality, distribution


def write_csv(path, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def summarize(rows, nodes):
    measured = [r for r in rows if r['phase'] == 'measured']
    ok = [r for r in measured if r['complete']]
    result = {'queries_attempted': len(measured), 'complete': len(ok),
              'failed_or_partial': len(measured)-len(ok),
              'client_ms_complete': distribution([r['client_ms'] for r in ok]),
              'all_attempt_hit_rate': sum(r.get('hit_at_k', 0) for r in measured)/len(measured),
              'quality_complete_only': {}, 'nodes': {}}
    for key in ('hit_at_k', 'miss_at_k', 'precision_at_k', 'judged_recall_at_k',
                'reciprocal_rank_at_k', 'judged_ndcg_at_k'):
        result['quality_complete_only'][key] = (sum(r[key] for r in ok)/len(ok)) if ok else None
    for node in sorted({r['node_id'] for r in nodes}):
        nr = [r for r in nodes if r['node_id'] == node and r['phase'] == 'measured']
        called = [r for r in nr if r['status'] == 'ok']
        judged = [r for r in called if r.get('hit_at_k') is not None]
        result['nodes'][node] = {'statuses': {s: sum(r['status']==s for r in nr) for s in
            ('ok', 'error', 'skipped', 'unknown')},
            'round_trip_ms': distribution([r['round_trip_ms'] for r in called]),
            'hit_rate_when_queried_and_observable': sum(r['hit_at_k'] for r in judged)/len(judged) if judged else None,
            'quality_observed_queries': len(judged),
            'request_body_bytes': sum(r.get('request_body_bytes', 0) for r in nr),
            'response_body_bytes': sum(r.get('response_body_bytes', 0) for r in nr)}
    return result


async def run(a):
    raw = a.queries.read_bytes()
    cases = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    if not cases or len({q['case_id'] for q in cases}) != len(cases):
        raise ValueError('Cases must be nonempty with unique case_id')
    for q in cases:
        if not q.get('relevant_hashes') or not q.get('query'):
            raise ValueError('query and nonempty relevant_hashes required')
        if not q.get('reviewed') and not a.allow_draft:
            raise ValueError('Unreviewed qrels: review evidence first, or use --allow-draft for pilot only')
    a.output.mkdir(parents=True, exist_ok=False)
    manifest = {k: str(v) if isinstance(v, Path) else v for k, v in vars(a).items()}
    manifest.update(query_set_sha256=hashlib.sha256(raw).hexdigest(),
                    quality_status='draft' if any(not q.get('reviewed') for q in cases) else 'reviewed',
                    note='retrieval only; node body bytes are not Ethernet bytes; no generation')
    (a.output/'manifest.json').write_text(json.dumps(manifest, indent=2))
    rows, nodes = [], []
    rng = random.Random(a.seed)
    async with httpx.AsyncClient(timeout=a.timeout, trust_env=False,
            headers={'x-api-key': os.getenv('BELLEQ_API_KEY', '')}) as client:
        with (a.output/'raw.jsonl').open('w') as out:
            # Sequential client load: unambiguous per-query windows; a later load test is separate.
            for iteration in range(a.warmup+a.repeat):
                phase = 'warmup' if iteration < a.warmup else 'measured'
                order = cases.copy()
                rng.shuffle(order)
                for case in order:
                    qid = str(uuid.uuid4())
                    payload = dict(query=case['query'], query_id=qid, top_k=a.top_k,
                                   per_node_k=a.per_node_k, mode=a.mode, min_score=a.min_score)
                    body = json.dumps(payload, ensure_ascii=False).encode()
                    start_epoch, start = time.time(), time.perf_counter()
                    record = dict(query_id=qid, case_id=case['case_id'], phase=phase,
                                  iteration=iteration, start_epoch=start_epoch, request=payload,
                                  request_body_bytes=len(body))
                    data = {}
                    try:
                        r = await client.post(a.url, content=body, headers={'Content-Type':'application/json'})
                        record.update(http_status=r.status_code, response_body_bytes=len(r.content))
                        data = r.json()
                        record['response'] = data
                    except Exception as exc:
                        record['error'] = str(exc)
                    record.update(end_epoch=time.time(), client_ms=(time.perf_counter()-start)*1000)
                    out.write(json.dumps(record, ensure_ascii=False)+'\n'); out.flush()
                    success = record.get('http_status') == 200 and not data.get('partial', True)
                    row = {k: record[k] for k in ('query_id','case_id','phase','iteration','start_epoch','end_epoch','client_ms')}
                    row.update(complete=success, http_status=record.get('http_status'), error=record.get('error'))
                    if success:
                        row.update(quality(data['chunks'], case['relevant_hashes'], a.top_k))
                    details = data.get('detail', data)
                    if not isinstance(details, dict): details = {}
                    row.update(details.get('timings', {}))
                    routing = details.get('routing', {})
                    row.update(target_reached=routing.get('target_reached'),
                               stop_reason=routing.get('stop_reason'),
                               visited_nodes=';'.join(routing.get('visited_nodes', [])))
                    statuses = {n['node_id']: n for n in details.get('nodes', [])}
                    for node in a.nodes:
                        n = statuses.get(node)
                        nr = dict(query_id=qid, case_id=case['case_id'], phase=phase, node_id=node,
                                  status='skipped' if node in routing.get('skipped_nodes', []) else 'unknown')
                        if n:
                            nr.update({k:v for k,v in n.items() if k not in ('timings','candidates')})
                            nr.update(n.get('timings', {}))
                            if n['status']=='ok' and 'candidates' in n:
                                candidates = [h for h in n['candidates'] if h['score'] >= a.min_score]
                                nr.update(quality(candidates, case['relevant_hashes'], a.top_k))
                                nr['quality_scope'] = 'node_candidates_against_global_judged_evidence'
                        nodes.append(nr)
                    rows.append(row)
                    print(phase, case['case_id'], 'ok' if success else 'failed', row.get('hit_at_k'), flush=True)
    write_csv(a.output/'queries.csv', rows)
    write_csv(a.output/'nodes.csv', nodes)
    (a.output/'summary.json').write_text(json.dumps(summarize(rows, nodes), indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url', default='http://192.168.50.11:8000/v1/retrieve/aggregate')
    p.add_argument('--queries', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--scenario', choices=['categorical','random_chunks','single_db'], required=True)
    p.add_argument('--mode', choices=['broadcast','semantic_sequential'], required=True)
    p.add_argument('--nodes', nargs='+', default=['mini-2','mini-3','mini-4'])
    p.add_argument('--top-k', type=int, default=3)
    p.add_argument('--per-node-k', type=int, default=5)
    p.add_argument('--min-score', type=float, default=.70)
    p.add_argument('--repeat', type=int, default=5)
    p.add_argument('--warmup', type=int, default=1, help='full query-set passes, recorded but excluded from summary')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--timeout', type=float, default=60)
    p.add_argument('--allow-draft', action='store_true')
    a=p.parse_args()
    if not (1 <= a.top_k <= 100 and a.top_k <= a.per_node_k <= 200 and
            -1 <= a.min_score <= 1 and a.repeat > 0 and a.warmup >= 0 and a.timeout > 0):
        p.error('Invalid k, threshold, repeat, warmup or timeout')
    asyncio.run(run(a))

if __name__ == '__main__': main()
