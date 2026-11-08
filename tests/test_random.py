import json,random
import httpx,pytest
from belleq_lab.app import create_app
from belleq_lab.config import Settings,Node
from test_service import FakeBackend,hit

@pytest.mark.asyncio
@pytest.mark.parametrize('sufficient',[True,False])
async def test_random_unique_order_threshold_and_stop(sufficient):
    names=['a','b','c'];order=list(names);random.Random(42).shuffle(order);calls=[]
    class Backend(FakeBackend):
        async def embed(self,*a,**kw):raise AssertionError('Random routing must not embed at coordinator')
    async def handle(req):
        calls.append(req.url.host);q=json.loads(req.content)
        chunks=[hit('shared',.9,'s'),hit('shared',.91,'s2')]
        if sufficient and req.url.host==order[1]:chunks += [hit('second',.85,'2'),hit('third',.8,'3')]
        chunks += [hit('low',.79,'low')]
        return httpx.Response(200,json=dict(node_id=req.url.host,query_id=q['query_id'],signature=FakeBackend.signature,fingerprint='same',chunks=chunks,timings={}))
    s=Settings(coordinator=True,nodes=[Node(id=n,url='http://'+n) for n in names])
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as network:
        app=create_app(s,Backend(),network)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://coordinator') as c:
                r=await c.post('/v1/retrieve/aggregate',json=dict(query='test',mode='random_sequential',random_seed=42,top_k=3,per_node_k=5,min_score=.8))
                assert r.status_code==200,r.text
                d=r.json();assert calls==order[:2] if sufficient else calls==order
                assert len(calls)==len(set(calls))
                assert all(h['score']>=.8 for h in d['chunks'])
                assert d['routing']['stop_reason']==('target_reached' if sufficient else 'all_nodes_visited')
                assert len(d['chunks'])==(3 if sufficient else 1)
