"""Local semantic catalogue ranking. No LLM and no worker discovery requests."""
import math


def cosine(left, right):
    if not left or len(left) != len(right):
        raise ValueError('Router vector dimensions differ')
    if not all(math.isfinite(x) for x in (*left, *right)):
        raise ValueError('Router vectors must be finite')
    ln = math.sqrt(sum(x*x for x in left))
    rn = math.sqrt(sum(x*x for x in right))
    if not ln or not rn:
        raise ValueError('Router vectors must be nonzero')
    return sum(x*y for x, y in zip(left, right)) / (ln*rn)


def rank_nodes(nodes, query_vector, catalogue_vectors):
    if len(nodes) != len(catalogue_vectors):
        raise ValueError('Router catalogue embedding count mismatch')
    ranked = [(n, cosine(query_vector, v)) for n, v in zip(nodes, catalogue_vectors)]
    return sorted(ranked, key=lambda pair: (-pair[1], pair[0].id))
