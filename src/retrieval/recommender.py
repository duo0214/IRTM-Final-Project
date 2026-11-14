"""C: seed phrases present in retrieved documents; this is not semantic mapping."""
def suggest(query, ranked_documents, seed_phrases, limit=6):
    candidates = []
    for phrase in seed_phrases:
        evidence = [d['doc_id'] for d in ranked_documents if phrase in d['text']]
        if evidence:
            candidates.append({'phrase': phrase, 'reason': '出現在本次檢索結果的種子詞組',
                               'source_doc_ids': evidence, 'method': 'seed_in_results',
                               'review_status': 'seed_not_human_validated'})
    return sorted(candidates, key=lambda x: (-int(x['phrase'] in query), -len(x['source_doc_ids']), x['phrase']))[:limit]
