"""Bounded concurrent requests, JSONL results; failed queries retained."""
import argparse
import asyncio
import json
import os
import time
import uuid
from pathlib import Path
import httpx

async def main():
    p=argparse.ArgumentParser()
    p.add_argument('--url',required=True)
    p.add_argument('--queries',type=Path,required=True,help='one query per line')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--concurrency',type=int,default=1)
    p.add_argument('--repeat',type=int,default=3)
    p.add_argument('--top-k',type=int,default=5)
    p.add_argument('--mode', choices=['broadcast','semantic_sequential'], default='broadcast')
    p.add_argument('--min-score', type=float, default=.70)
    p.add_argument('--per-node-k', type=int, default=5)
    a=p.parse_args()
    if a.concurrency<1 or a.repeat<1: p.error('positive concurrency/repeat required')
    queries=[q.strip() for q in a.queries.read_text().splitlines() if q.strip()]
    sem=asyncio.Semaphore(a.concurrency)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    async with httpx.AsyncClient(timeout=300,trust_env=False,
                                headers={'x-api-key':os.getenv('BELLEQ_API_KEY','')}) as c:
        with a.output.open('w') as out:
            async def run(query,iteration):
                async with sem:
                    qid=str(uuid.uuid4()); start=time.perf_counter()
                    body=json.dumps({'query':query,'top_k':a.top_k,'per_node_k':a.per_node_k,
                                     'mode':a.mode,'min_score':a.min_score,'query_id':qid},ensure_ascii=False).encode()
                    row={'query_id':qid,'iteration':iteration,'query':query,'request_body_bytes':len(body)}
                    try:
                        r=await c.post(a.url,content=body,headers={'content-type':'application/json'})
                        row.update(status=r.status_code,response_body_bytes=len(r.content),response=r.json())
                    except Exception as exc: row['error']=str(exc)
                    row['client_ms']=(time.perf_counter()-start)*1000
                    out.write(json.dumps(row,ensure_ascii=False)+'\n'); out.flush()
            await asyncio.gather(*(run(q,i) for i in range(a.repeat) for q in queries))
if __name__=='__main__': asyncio.run(main())
