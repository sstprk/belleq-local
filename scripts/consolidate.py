"""Copy verified vectors/payloads into an empty, already-initialized Qdrant collection.

Use SSH forwards to loopback-only Qdrant services. This never deletes a collection.
"""
import argparse
import json
from pathlib import Path
import httpx


def consolidate(client,sources,destination,collection):
    def call(method,base,path,**kw):
        response=client.request(method,base.rstrip('/')+path,**kw)
        response.raise_for_status()
        return response.json()['result']
    path='/collections/'+collection
    if call('POST',destination,path+'/points/count',json={'exact':True})['count']!=0:
        raise ValueError('Destination must be empty; no data is deleted automatically')
    schemas=[]
    for base in [*sources,destination]:
        result=call('POST',base,path+'__schema/points/scroll',
                    json={'limit':2,'with_payload':True,'with_vector':False})
        schemas.append({p['payload']['fingerprint'] for p in result['points']})
    if any(len(s)!=1 or s!=schemas[0] for s in schemas):
        raise ValueError('Embedding schemas differ or an API has not initialized its collection')
    seen=set();report={}
    for source in sources:
        offset=None;count=0;maxdiff=0.0
        while True:
            body={'limit':128,'with_payload':True,'with_vector':True}
            if offset is not None:body['offset']=offset
            result=call('POST',source,path+'/points/scroll',json=body)
            points=result['points']
            if any(p['id'] in seen for p in points):
                raise ValueError('Source partitions overlap; use disjoint categorical partitions')
            seen.update(p['id'] for p in points)
            if points:
                call('PUT',destination,path+'/points?wait=true',json={'points':points})
                fetched=call('POST',destination,path+'/points',json={
                    'ids':[p['id'] for p in points],'with_payload':True,'with_vector':True})
                lookup={p['id']:p for p in fetched}
                for p in points:
                    q=lookup[p['id']]
                    if p['payload']!=q['payload'] or len(p['vector'])!=len(q['vector']):
                        raise ValueError('Copied payload/vector shape mismatch')
                    delta=max(abs(x-y) for x,y in zip(p['vector'],q['vector']))
                    if delta>1e-6:raise ValueError('Copied vectors changed')
                    maxdiff=max(maxdiff,delta)
            count+=len(points);offset=result.get('next_page_offset')
            if offset is None:break
        report[source]={'points':count,'max_vector_component_difference':maxdiff}
    total=call('POST',destination,path+'/points/count',json={'exact':True})['count']
    if total!=len(seen):raise ValueError('Destination point count mismatch')
    return {'sources':report,'total':total,'payloads_verified':True,'schemas_verified':True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sources',nargs='+',required=True)
    p.add_argument('--destination',required=True)
    p.add_argument('--collection',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():p.error('Output exists; choose a fresh path')
    with httpx.Client(timeout=120,trust_env=False) as c:
        report=consolidate(c,a.sources,a.destination,a.collection)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':main()
