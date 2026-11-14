"""D: actual document-level Jaccard, not semantic/causal/legal relations."""
def related_terms(term, phrase_index, seed_phrases, limit=5):
    a = {d['doc_id'] for d in phrase_index.lookup(term)['documents']}
    result = []
    for other in seed_phrases:
        if other == term:
            continue
        b = {d['doc_id'] for d in phrase_index.lookup(other)['documents']}
        common = a & b
        if common:
            result.append({'phrase': other, 'score': len(common)/len(a | b),
                           'cooccurrence_df': len(common), 'method': 'document_jaccard'})
    return sorted(result, key=lambda d: (-d['score'], d['phrase']))[:limit]

def context(text, start, end, window=36):
    left, right = max(0, start-window), min(len(text), end+window)
    return {'text': text[left:right], 'context_start': left,
            'match_start': start-left, 'match_end': end-left}
