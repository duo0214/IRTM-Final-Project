"""B's correctness oracle, NOT a PAT-tree. Supports overlapping literal matches."""
def positions(text, phrase):
    if not phrase:
        raise ValueError('phrase cannot be blank')
    start = 0
    hits = []
    while True:
        start = text.find(phrase, start)
        if start < 0:
            return hits
        hits.append({'start': start, 'end': start + len(phrase)})
        start += 1

class ReferencePhraseIndex:
    backend = 'reference_scan_not_pat_tree'

    def __init__(self, documents):
        self.documents = documents

    def lookup(self, phrase):
        matches = []
        for doc in self.documents:
            hits = positions(doc['text'], phrase)
            if hits:
                matches.append({'doc_id': doc['doc_id'], 'tf': len(hits), 'positions': hits})
        return {'phrase': phrase, 'frequency': sum(d['tf'] for d in matches),
                'df': len(matches), 'documents': matches, 'backend': self.backend}
