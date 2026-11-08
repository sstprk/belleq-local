"""Reproducible audit, grouped split, candidate model training and frozen test."""
from collections import Counter
from itertools import permutations
import json
import platform
import numpy as np
from .common import ROOT, METHODS, SEED, csv_read, csv_write, jsonl, write_json, event, distribution, empirical_ci, sha256
from .ridge import fit, predict, features, FEATURE_NAMES, metrics
from .replay import replay

TARGETS = ['aggregate_ms','network_frame_bytes','client_ms']

def raw_records():
    paths=[ROOT/'data/raw/oct12/responses.jsonl'] + [ROOT/'data/raw/oct14'/s/'responses.jsonl'
          for s in ['random_node_order','single_db','random_node_order_t070','single_db_t070']]
    return [r for p in paths for r in jsonl(p) if r['phase']=='measured']

def payload(r):
    d=r.get('response',{})
    if isinstance(d.get('detail'),dict):d=d['detail']
    return d.get('retrieval',d)

def is_complete(r):
    return r['complete']=='True'

def fit_baseline(rows, target):
    return {m:float(np.mean([r[target] for r in rows if r['experiment_method']==m])) for m in METHODS}

def scalar_record(r):
    return dict(sample_id=r['sample_id'],case_id=r['case_id'],method=r['experiment_method'],
                complete=is_complete(r),aggregate_ms=float(r['aggregate_ms']) if r['aggregate_ms'] else None,
                client_ms=float(r['client_ms']),network_frame_bytes=r['network_frame_bytes'],
                body_bytes=r['body_bytes'],visited_nodes=float(r['visited_node_count'] or 0),
                hit=float(r['hit_at_k']) if r['hit_at_k'] else None,
                generation_ms=float(r['generation_ms'] or 0),generation_invoked=r['generation_invoked']=='True',
                question=r['question'],run_id=r['run_id'])

def main():
    event('02_audit_started')
    rows=csv_read(ROOT/'data/raw/combined_070.csv')
    assert len(rows)==2000 and len({r['sample_id'] for r in rows})==2000
    assert all(float(r['min_score'])==.7 for r in rows)
    assert set(Counter(r['case_id'] for r in rows).values())=={4}
    assert len({r['question_set_sha256'] for r in rows})==1
    assert len({r['corpus_sha256'] for r in rows})==1
    raw=raw_records();by_uuid={r['query_id']:r for r in raw}
    assert all(r['sample_id'] in by_uuid for r in rows)
    lookup={}
    for r in rows:
        qid=r['case_id'];rr=by_uuid[r['sample_id']];d=payload(rr)
        r['network_frame_bytes']=float(r['mini1_network_tx_bytes'])+float(r['mini1_network_rx_bytes'])
        r['body_bytes']=sum(n.get('request_body_bytes',0)+n.get('response_body_bytes',0) for n in d.get('nodes',[]))
        for k in ['aggregate_ms','client_ms']:
            r[k]=float(r[k]) if r[k] else None
        lookup[qid,r['experiment_method']]=rr
        assert r['question']==rr['query']
        if is_complete(r):
            assert not d['partial']
            assert int(r['returned'])==len(d['chunks'])
    ids=np.array(sorted({r['case_id'] for r in rows}))
    rng=np.random.default_rng(SEED);rng.shuffle(ids)
    split={q:('train' if i<300 else 'validation' if i<400 else 'test') for i,q in enumerate(ids)}
    write_json(ROOT/'artifacts/split.json',dict(seed=SEED,unit='case_id',assignments=split,
                 counts=dict(Counter(split.values())),note='All methods and derived augmentations inherit their parent question split.'))
    for r in rows:r['split']=split[r['case_id']]
    csv_write(ROOT/'data/processed/observations.csv',rows)
    audit=dict(rows=len(rows),questions=len(ids),methods=dict(Counter(r['experiment_method'] for r in rows)),
               failed=sum(not is_complete(r) for r in rows),split_counts=dict(Counter(split.values())),
               books=len({r['book_id'] for r in rows}),chunks=16421,
               missing_network_rows=sum(not r['mini1_network_duration_s'] for r in rows),
               feature_caveat='Only 1 and 3 search nodes; node count confounded with method; no learned node-count, corpus-size, bandwidth, or load coefficient.',
               clock_caveat='Host wall clocks unsynchronized; same-host windows valid; run/session effects remain.',
               quality_caveat='Synthetic nonexhaustive source-passage labels; no answer correctness assessment.',
               incomplete_rtt_note='Old PCAP trailing record repaired; drop count unknown. Restart PCAP has zero kernel drops.',
               input_sha256=sha256(ROOT/'data/raw/combined_070.csv'))
    write_json(ROOT/'results/data_audit.json',audit)
    event('02_audit_complete',**audit)

    # Train on real observations only. Synthetic permutations are never used as independent labels.
    model_report={};model_store={};pred_rows=[]
    for target in TARGETS:
        usable=[r for r in rows if is_complete(r) and r[target] is not None]
        parts={s:[r for r in usable if r['split']==s] for s in ['train','validation','test']}
        train,val,test=[parts[s] for s in ['train','validation','test']]
        x=lambda rr:np.array([features(r) for r in rr]);y=lambda rr:np.array([r[target] for r in rr])
        candidates=[]
        for alpha in [.1,1,10,100,1000]:
            mod=fit(x(train),y(train),alpha)
            candidates.append((metrics(y(val),predict(mod,x(val)))['mae'],alpha))
        best_mae,alpha=min(candidates)
        baseline=fit_baseline(train,target)
        val_base=metrics(y(val),[baseline[r['experiment_method']] for r in val])
        selected='ridge' if best_mae<val_base['mae'] else 'method_mean'
        calibration=train+val
        final=fit(x(calibration),y(calibration),alpha)
        base_final=fit_baseline(calibration,target)
        pred=predict(final,x(test));bp=np.array([base_final[r['experiment_method']] for r in test])
        selected_pred=pred if selected=='ridge' else bp
        for r,p,b in zip(test,pred,bp):
            pred_rows.append(dict(case_id=r['case_id'],sample_id=r['sample_id'],method=r['experiment_method'],
                target=target,observed=r[target],ridge=float(p),baseline=float(b),
                selected=float(p if selected=='ridge' else b)))
        model_store[target]=dict(selected=selected,ridge=final,method_mean=base_final,
            features=FEATURE_NAMES,calibration_cases=400,test_cases_excluded=100)
        model_report[target]=dict(selected_on_validation=selected,alpha=alpha,
            validation_ridge_mae=best_mae,validation_baseline=val_base,
            alpha_search=[dict(alpha=a,validation_mae=e) for e,a in candidates],
            frozen_test_ridge=metrics(y(test),pred),frozen_test_baseline=metrics(y(test),bp),
            frozen_test_selected=metrics(y(test),selected_pred),
            by_method={m:metrics([r[target] for r in test if r['experiment_method']==m],
                               [float(p) for r,p in zip(test,selected_pred) if r['experiment_method']==m]) for m in METHODS})
    write_json(ROOT/'artifacts/regressors.json',model_store)
    write_json(ROOT/'results/model_validation.json',model_report)
    csv_write(ROOT/'results/test_predictions.csv',pred_rows)
    event('03_models_trained',targets=TARGETS,train_questions=300,validation_questions=100,
          frozen_test_questions=100,augmentation_used_for_regression=False)

    # Empirical Monte Carlo calibration keeps correlated metrics in the same query row.
    cal=[scalar_record(r) for r in rows if r['split']!='test']
    write_json(ROOT/'artifacts/calibration.json',cal)
    validation=[];boot_rng=np.random.default_rng(SEED+1)
    for m in METHODS:
        a=[r for r in rows if r['experiment_method']==m and r['split']!='test' and is_complete(r)]
        b=[r for r in rows if r['experiment_method']==m and r['split']=='test' and is_complete(r)]
        for target in TARGETS:
            av=[r[target] for r in a];bv=[r[target] for r in b]
            sim=boot_rng.choice(av,size=10000,replace=True)
            da,db=distribution(sim),distribution(bv)
            validation.append(dict(method=m,target=target,calibration_n=len(a),test_n=len(b),
                simulated_mean=da['mean'],test_mean=db['mean'],mean_error_percent=100*(da['mean']/db['mean']-1),
                simulated_p95=da['p95'],test_p95=db['p95'],
                p95_error_percent=100*(da['p95']/db['p95']-1),
                calibration_mean_ci_low=empirical_ci(av)[0],calibration_mean_ci_high=empirical_ci(av)[1]))
    csv_write(ROOT/'results/monte_carlo_validation.csv',validation)
    event('04_monte_carlo_validated',draws=10000,independent_test_questions=100,
          note='Distribution-level validation, not query-specific latency prediction or unseen-node-count validation.')

    # Verify faithful replay against ALL recorded successful .70 runs (algorithm check only).
    questions={q['case_id']:q for q in jsonl(ROOT/'data/raw/oct12/questions.generated.jsonl')}
    comparisons=[];trace_library=[];augmentation=[]
    for qid in sorted(questions):
        broadcast=payload(lookup[qid,'broadcast'])
        nodes={n['node_id']:n for n in broadcast['nodes']}
        for m in METHODS:
            rr=lookup[qid,m]
            if rr['http_status']!=200:continue
            d=payload(rr);actual_nodes={n['node_id']:n for n in d['nodes']}
            order=d['routing']['visited_nodes']
            visited,hits=replay(actual_nodes,order,'broadcast' if m in ['broadcast','single_db'] else m)
            actual=[h['content_hash'] for h in d['chunks']]
            comparisons.append(dict(case_id=qid,method=m,visits_match=visited==order,
                                    hashes_match=[h['content_hash'] for h in hits]==actual))
        sem=lookup[qid,'semantic_sequential'];dsem=payload(sem)
        sem_order=[n['node_id'] for n in dsem.get('routing',{}).get('ranking',[])]
        if len(sem_order)!=3:sem_order=sorted(nodes)
        for i,order in enumerate(permutations(sorted(nodes))):
            visited,hits=replay(nodes,order,'random_sequential')
            augmentation.append(dict(case_id=qid,split=split[qid],order_id=i,order='|'.join(order),
                visited='|'.join(visited),visits=len(visited),returned=len(hits),
                reference_hit=int(any(h['content_hash'] in questions[qid]['relevant_hashes'] for h in hits)),
                application_body_bytes=sum(nodes[n]['request_body_bytes']+nodes[n]['response_body_bytes'] for n in visited),
                rtt_sum_ms=sum(nodes[n]['round_trip_ms'] for n in visited),
                label_type='counterfactual_from_old_broadcast_candidates_not_new_measurement'))
        if split[qid]!='test':
            trace_library.append(dict(case_id=qid,split=split[qid],question=questions[qid]['query'],
                owner=questions[qid]['expected_node'],gold=questions[qid]['relevant_hashes'],
                semantic_order=sem_order,router_ms=dsem.get('timings',{}).get('router_ms',291),nodes=nodes))
    csv_write(ROOT/'results/replay_validation.csv',comparisons)
    assert all(r['hashes_match'] and r['visits_match'] for r in comparisons)
    csv_write(ROOT/'data/augmented/order_permutations.csv',augmentation)
    write_json(ROOT/'artifacts/trace_library.json',trace_library)
    assert len(trace_library)==400
    event('05_replay_and_augmentation',replay_checks=len(comparisons),all_match=True,
          derived_rows=len(augmentation),independent_questions=500,
          deployment_trace_questions=400,rule='Augmentations inherit split; test derivatives never calibrate deployed model.')

    aux=[]
    for scenario in ['random_node_order','single_db']:
        rr=[r for r in raw if r['scenario']==scenario]
        hits=0;generation=0;empty=0
        for r in rr:
            d=payload(r);q=questions[r['case_id']]
            hits+=any(h['content_hash'] in q['relevant_hashes'] for h in d['chunks'])
            generation+=d.get('generation_ms',0)>0
            empty+=not d['chunks']
        aux.append(dict(scenario=scenario,threshold=.8,n=len(rr),hits=hits,
                        generation_invoked=generation,no_context=empty,usage='auxiliary_only_not_main_training'))
    write_json(ROOT/'results/threshold_080_auxiliary.json',aux)
    observed=[]
    for m in METHODS:
        rr=[r for r in rows if r['experiment_method']==m];ok=[r for r in rr if is_complete(r)]
        observed.append(dict(method=m,n=len(rr),complete=len(ok),hits=sum(int(r['hit_at_k'] or 0) for r in rr),
            generation_invoked=sum(r['generation_invoked']=='True' for r in rr),
            aggregate_ms=distribution([r['aggregate_ms'] for r in ok]),
            client_ms=distribution([r['client_ms'] for r in ok]),
            network_frame_bytes=distribution([r['network_frame_bytes'] for r in rr])))
    write_json(ROOT/'results/observed_summary.json',observed)
    write_json(ROOT/'artifacts/model_card.json',dict(version='0.1.0',seed=SEED,
        calibration_questions=400,frozen_test_questions=100,real_observations=2000,
        synthetic_permutations=3000,unseen_node_count_validated=False,
        learned_node_count_coefficient=False,queueing_validated=False,
        empirical_scope='M2 8GB; 12 books; 16421 chunks; concurrency 1; .70; top_k 3; per_node_k 5; native 1/3 search nodes',
        unsupported=['random data placement','hardware transfer','load/queue capacity','corpus-size scaling','new-model token speed'],
        python=platform.python_version(),numpy=np.__version__))
    print('Training and frozen validation complete. Replay checks:',len(comparisons))

if __name__=='__main__':main()
