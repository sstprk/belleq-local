import asyncio
import hashlib
import json
from contextlib import AsyncExitStack
import httpx
import pytest
from belleq_lab.app import create_app, merge_results
from belleq_lab.config import Settings, Node
from belleq_lab.chunker import chunk_text, make_point_id


def hit(text='evidence', score=0.8, id='a'):
    return dict(id=id, score=score, text=text, doc_id='doc', source='test.txt',
                doc_title='Test', chunk_index=0)

class FakeBackend:
    signature = {'model': 'test', 'digest': 'same'}
    fingerprint = 'same'
    def __init__(self, hits=None):
        self.hits = hits if hits is not None else [hit()]
        self.calls = []
    async def initialize(self): pass
    async def request(self, method, base, path):
        return {'models': [{'name': 'nomic-embed-text:latest', 'digest': 'same'}]}
    async def embed(self, texts, query=False): return [[1., 0.]]
    async def search(self, vector, top_k): return self.hits[:top_k]
    async def ingest(self, text, title, source):
        return dict(doc_id='doc', chunks=len(chunk_text(text)), embedding_ms=1)
    async def generate(self, question, context):
        self.calls.append(context)
        return {'message': {'content': 'answer [1]'}}

@pytest.mark.asyncio
async def test_real_asgi_fanout_self_local_and_answer():
    """Three application nodes, real route dispatch; only model/DB dependencies are fakes."""
    apps, transports = {}, {}
    async def dispatch(request):
        return await transports[request.url.host].handle_async_request(request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(dispatch)) as network:
        async with AsyncExitStack() as stack:
            for name in ('mini-1', 'mini-2', 'mini-3'):
                s = Settings(node_id=name, coordinator=name=='mini-1', nodes=[
                    Node(id=n, url='http://'+n) for n in ('mini-1','mini-2','mini-3')])
                b = FakeBackend([hit('shared', .8, 'a'), hit(name, .9, name)])
                app = create_app(s, b, network)
                await stack.enter_async_context(app.router.lifespan_context(app))
                apps[name] = app
                transports[name] = httpx.ASGITransport(app=app)
            r = await network.post('http://mini-1/v1/answer', json={'query': 'test', 'top_k': 4})
            assert r.status_code == 200, r.text
            data = r.json()
            assert not data['partial'] and len(data['nodes']) == 3
            assert len(data['chunks']) == 4
            assert len(next(h for h in data['chunks'] if h['text']=='shared')['locations']) == 3
            assert data['answer'] == 'answer [1]'
            assert len(apps['mini-1'].state.backend.calls) == 1
            assert data['traffic']['response_bytes'] > 0
            assert all('embedding_ms' in n['timings'] for n in data['nodes'])
            assert all(len(n['candidates']) == 2 for n in data['nodes'])
            assert all('text' not in h for n in data['nodes'] for h in n['candidates'])
            denied = await network.post('http://mini-2/v1/retrieve/aggregate', json={'query':'test'})
            assert denied.status_code == 403

async def run_aggregate(handler, payload=None):
    s = Settings(coordinator=True, node_timeout=.03, nodes=[Node(id='good', url='http://good'), Node(id='bad', url='http://bad')])
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as network:
        app = create_app(s, FakeBackend(), network)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                return await client.post('/v1/retrieve/aggregate', json=payload or {'query':'test'})

def reply(request):
    q = json.loads(request.content)
    return {'node_id': request.url.host, 'query_id':q['query_id'], 'fingerprint':'same',
            'signature': FakeBackend.signature, 'chunks':[hit()], 'timings':{'search_ms':1}}

@pytest.mark.parametrize('mode', ['timeout','schema','identity','http','malformed'])
async def test_failure_strict_and_partial(mode):
    async def handler(request):
        data = reply(request)
        if request.url.host=='bad':
            if mode=='timeout': await asyncio.sleep(.2)
            if mode=='schema': data['fingerprint']='different'
            if mode=='identity': data['node_id']='wrong'
            if mode=='http': return httpx.Response(500)
            if mode=='malformed': data['chunks']=[{'text':'bad'}]
        return httpx.Response(200, json=data)
    strict = await run_aggregate(handler)
    assert strict.status_code==503
    assert strict.json()['detail']['failed_nodes']==['bad']
    partial = await run_aggregate(handler, {'query':'test','allow_partial':True})
    assert partial.status_code==200 and partial.json()['partial']

async def test_all_failed_never_success():
    async def fail(request): return httpx.Response(503)
    r = await run_aggregate(fail, {'query':'test','allow_partial':True})
    assert r.status_code==503

async def test_local_upload_and_auth():
    app = create_app(Settings(api_key='test-key'), FakeBackend())
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as c:
            assert (await c.get('/health/live')).status_code==401
            c.headers['x-api-key']='test-key'
            r = await c.post('/v1/documents/upload', files={'file':('test.txt',b'Hello Belleq','text/plain')})
            assert r.status_code==200 and r.json()['chunks']==1
            assert (await c.post('/query',json={'query':'hello'})).status_code==200
            assert (await c.post('/query',json={'query':'   '})).status_code==422

async def test_context_budget_no_evidence_no_generation():
    async def handler(request): return httpx.Response(200,json=reply(request))
    s=Settings(coordinator=True, context_chars=1, nodes=[Node(id='good',url='http://good')])
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as network:
        b=FakeBackend(); app=create_app(s,b,network)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
                r=await c.post('/v1/answer',json={'query':'test'})
                assert r.status_code==200 and not b.calls
                assert r.json()['context_chunks']==[]


def test_merge_score_dedup_and_ties():
    result=merge_results([('a',[hit('same',.1,'1'),hit('other',.9,'2')]),
                          ('b',[hit('same',.99,'3')])],2)
    assert result[0]['score']==.99
    assert len(result[0]['locations'])==2


def test_chunking_stable_and_exact_source():
    text='Sentence. '*200
    assert chunk_text(text)==chunk_text(text)
    assert make_point_id('doc',0)==make_point_id('doc',0)
    assert make_point_id('doc',0)!=make_point_id('doc',1)
