"""E: small tested metric reference, not completed Benchmark results."""
import math

def evaluate(runs, qrels):
    """Input maps query IDs to ranked unique doc IDs / {doc_id: graded relevance}.
    Grades 0..2, binary relevance >0 for MRR/Recall; all judged queries averaged.
    No-positive queries are errors, never silently discarded.
    """
    if not qrels:
        raise ValueError('qrels is empty')
    details = []
    if set(runs) - set(qrels):
        raise ValueError('run contains unknown query IDs')
    for qid, judgments in sorted(qrels.items()):
        if any(not isinstance(v, int) or v not in (0,1,2) for v in judgments.values()):
            raise ValueError('relevance must be integer 0, 1 or 2')
        relevant = {d for d,v in judgments.items() if v > 0}
        if not relevant:
            raise ValueError('Query has no positive judgments: ' + qid)
        ranked = runs.get(qid, [])
        if len(ranked) != len(set(ranked)):
            raise ValueError('duplicate document in ranking')
        rr = next((1/i for i,d in enumerate(ranked[:10],1) if d in relevant), 0)
        recall = len(set(ranked[:5]) & relevant)/len(relevant)
        dcg = sum((2**judgments.get(d,0)-1)/math.log2(i+1) for i,d in enumerate(ranked[:10],1))
        ideal = sum((2**v-1)/math.log2(i+1) for i,v in enumerate(sorted(judgments.values(), reverse=True)[:10],1))
        details.append({'query_id': qid, 'MRR@10': rr, 'Recall@5': recall, 'nDCG@10': dcg/ideal})
    return {'query_count': len(details), 'metrics': {k:sum(d[k] for d in details)/len(details) for k in ('MRR@10','Recall@5','nDCG@10')}, 'per_query': details}
