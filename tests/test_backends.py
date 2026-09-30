"""HTTP contract tests for adapters, with actual embedded Qdrant vector search."""
import json
import httpx
import pytest
from qdrant_client import QdrantClient, models
from belleq_lab.backends import Backends
from belleq_lab.config import Settings

@pytest.fixture
def database():
    db=QdrantClient(':memory:')
    yield db
    db.close()

async def test_ingestion_schema_restart_and_search(database):
    async def handle(req):
        body=json.loads(req.content) if req.content else {}
        path=req.url.path
        if path=='/api/tags':
            return httpx.Response(200,json={'models':[{'name':'nomic-embed-text:latest','digest':'abc'}]})
        if path=='/api/embed':
            return httpx.Response(200,json={'embeddings':[[1.,0.] for t in body['input']]})
        parts=path.strip('/').split('/'); col=parts[1]
        if len(parts)==2:
            if req.method=='PUT':
                database.create_collection(col, vectors_config=models.VectorParams(**body['vectors']))
                return httpx.Response(200,json={'result':True})
            if not database.collection_exists(col): return httpx.Response(404)
            info=database.get_collection(col)
            return httpx.Response(200,json={'result':json.loads(info.model_dump_json())})
        if path.endswith('/count'):
            result={'count':database.count(col,exact=True).count}
        elif path.endswith('/query'):
            points=database.query_points(col,query=body['query'],limit=body['limit'],
                query_filter=models.Filter(**body['filter']),with_payload=True).points
            result={'points':[json.loads(p.model_dump_json()) for p in points]}
        elif req.method=='PUT':
            database.upsert(col,[models.PointStruct(**p) for p in body['points']]); result=True
        else:
            result=[json.loads(p.model_dump_json()) for p in database.retrieve(col,body['ids'])]
        return httpx.Response(200,json={'result':result})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        settings=Settings(embedding_dimension=2)
        b=Backends(settings,client)
        await b.initialize()
        first=await b.ingest('Hello knowledge','Title','doc.txt')
        await b.ingest('Hello knowledge','Title','doc.txt')
        assert database.count('lab').count==1
        hits=await b.search([1.,0.],5)
        assert hits[0]['doc_id']==first['doc_id'] and hits[0]['score']==pytest.approx(1)
        # Restart is accepted; different embedding preprocessing is rejected.
        await Backends(settings,client).initialize()
        with pytest.raises(ValueError,match='schema differs'):
            await Backends(settings.model_copy(update={'query_prefix':'different'}),client).initialize()

async def test_bad_dimension_rejected():
    async def handle(req): return httpx.Response(200,json={'embeddings':[[1.]]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError,match='shape'):
            await Backends(Settings(embedding_dimension=2),client).embed(['x'])
