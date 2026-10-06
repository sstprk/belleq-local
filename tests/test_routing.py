import asyncio
import json
import httpx
import pytest
from belleq_lab.app import create_app
from belleq_lab.config import Settings, Node
from belleq_lab.routing import cosine
from test_service import FakeBackend, hit

class RouterBackend(FakeBackend):
    def __init__(self):
        super().__init__()
        self.embed_calls = []
    async def embed(self, texts, query=False):
        self.embed_calls.append((texts, query))
        if query:
            return [[1., 0.]]
        # mini-3 first, mini-2 second, mini-4 last.
        return [[.5,.5],[1.,0.],[0.,1.]]

async def scenario(results, payload=None, endpoint='/v1/retrieve/aggregate', repeat=1, strict=False):
    visited=[]
    async def handle(req):
        assert req.url.path == '/v1/retrieve/local'
        node=req.url.host
        visited.append(node)
        value=results[node]
        if value == 'timeout':
            await asyncio.sleep(.2)
        if value == 'http':
            return httpx.Response(503)
        q=json.loads(req.content)
        return httpx.Response(200,json={'node_id':node,'query_id':q['query_id'],
            'fingerprint':'wrong' if value == 'mismatch' else 'same',
            'signature':FakeBackend.signature,'chunks':[] if isinstance(value,str) else value,
            'timings':{'embedding_ms':1,'search_ms':1}})
    s=Settings(coordinator=True,retrieval_mode='semantic_sequential',node_timeout=.025,
        nodes=[Node(id=n,url='http://'+n,description=n+' book')
               for n in ('mini-2','mini-3','mini-4')])
    b=RouterBackend()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as network:
        app=create_app(s,b,network)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
                responses=[]
                for _ in range(repeat):
                    responses.append(await c.post(endpoint,json=payload or {'query':'question'}))
    return responses,visited,b


def hits(*names, score=.8):
    return [hit(name,score,name) for name in names]

async def test_three_unique_hits_stop_before_other_workers_and_answer():
    responses,visited,b=await scenario({'mini-3':hits('a','b','c')},endpoint='/v1/answer')
    assert responses[0].status_code==200, responses[0].text
    r=responses[0].json()
    assert visited==['mini-3']
    assert r['routing']['skipped_nodes']==['mini-2','mini-4']
    assert r['routing']['target_reached']
    assert len(r['context_chunks'])==3 and len(b.calls)==1
    assert len(r['nodes'])==1 and not r['partial']
    assert r['traffic']['request_bytes']==r['nodes'][0]['request_body_bytes']

async def test_accumulate_across_nodes_and_deduplicate_before_stop():
    responses,visited,b=await scenario({'mini-3':hits('a','a','b'),
        'mini-2':hits('a','c'), 'mini-4':hits('never')})
    assert visited==['mini-3','mini-2']
    r=responses[0].json()
    assert {h['text'] for h in r['chunks']}=={'a','b','c'}
    assert r['routing']['stop_reason']=='target_reached'

async def test_low_scores_do_not_count_and_exhaustion_is_explicit():
    responses,visited,b=await scenario({'mini-3':hits('a','b','c',score=.69),
        'mini-2':hits('d',score=.70),'mini-4':[]})
    r=responses[0].json()
    assert r['nodes'][0]['accepted_chunks']==0
    assert len(r['chunks'])==1 and not r['routing']['target_reached']
    assert r['routing']['stop_reason']=='all_nodes_visited'
    assert visited==['mini-3','mini-2','mini-4']
    assert not r['partial']  # insufficient relevance is not a transport failure

@pytest.mark.parametrize('failure',['timeout','http','mismatch'])
@pytest.mark.parametrize('partial',[True,False])
async def test_failure_continues_to_next_worker_but_preserves_error_policy(failure,partial):
    responses,visited,b=await scenario({'mini-3':failure,'mini-2':hits('a','b','c')},
        {'query':'question','allow_partial':partial})
    assert visited==['mini-3','mini-2']
    assert responses[0].status_code==(200 if partial else 503)
    r=responses[0].json() if partial else responses[0].json()['detail']
    assert r['failed_nodes']==['mini-3'] and r['routing']['target_reached']

async def test_broadcast_override_no_router_calls_and_same_threshold():
    responses,visited,b=await scenario({n:hits(n,score=.6) for n in ('mini-2','mini-3','mini-4')},
        {'query':'question','mode':'broadcast','min_score':.7})
    assert set(visited)=={'mini-2','mini-3','mini-4'}
    assert not b.embed_calls
    assert responses[0].json()['chunks']==[]

async def test_catalogue_embedded_once_queries_not_cached():
    responses,visited,b=await scenario({'mini-3':hits('a','b','c')},repeat=2)
    assert len([x for x in b.embed_calls if not x[1]])==1
    assert len([x for x in b.embed_calls if x[1]])==2
    assert responses[0].json()['routing']['catalogue_built']
    assert not responses[1].json()['routing']['catalogue_built']

async def test_missing_descriptions_fail_without_worker_requests():
    s=Settings(coordinator=True,nodes=[Node(id='node',url='http://node')])
    async def never(req): raise AssertionError('worker must not be called')
    async with httpx.AsyncClient(transport=httpx.MockTransport(never)) as network:
        app=create_app(s,FakeBackend(),network)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
                r=await c.post('/v1/retrieve/aggregate',json={'query':'test','mode':'semantic_sequential'})
                assert r.status_code==422


def test_cosine_rejects_invalid_vectors():
    for a,b in [([0,0],[1,0]),([1],[1,0]),([float('nan')],[1])]:
        with pytest.raises(ValueError): cosine(a,b)
