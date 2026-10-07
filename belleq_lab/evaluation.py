"""Placement-independent, binary judged-evidence metrics (not cosine thresholds)."""
import math


def quality(hits, relevant_hashes, k):
    gold = set(relevant_hashes)
    if not gold:
        raise ValueError('An answerable query needs at least one judged evidence hash')
    seen, flags = set(), []
    for h in hits[:k]:
        key = h.get('content_hash')
        flags.append(int(key in gold and key not in seen))
        seen.add(key)
    found = sum(flags)
    return {'hit_at_k': int(found > 0), 'miss_at_k': int(found == 0),
            'precision_at_k': found / k, 'judged_recall_at_k': found / len(gold),
            'reciprocal_rank_at_k': next((1 / (i+1) for i, x in enumerate(flags) if x), 0.0),
            'judged_ndcg_at_k': sum(x / math.log2(i+2) for i, x in enumerate(flags)) /
                sum(1 / math.log2(i+2) for i in range(min(k, len(gold)))),
            'relevant_returned': found, 'returned': len(hits[:k]), 'gold_count': len(gold)}


def distribution(values):
    values = sorted(values)
    if not values:
        return {'n': 0, 'mean': None, 'p50': None, 'p95': None}
    def percentile(p):
        x = (len(values)-1)*p
        lo, hi = math.floor(x), math.ceil(x)
        return values[lo] + (values[hi]-values[lo])*(x-lo)
    return {'n': len(values), 'mean': sum(values)/len(values),
            'p50': percentile(.5), 'p95': percentile(.95)}
