"""Shared contract checks; A owns rules, every contributor runs them."""
import hashlib
import json
from pathlib import Path

def validate_records(records, corpus_id=None):
    seen = set()
    for i, d in enumerate(records, 1):
        for key in ('schema_version','corpus_id','doc_id','law_id','law_name','article_no','text','domain','source_url','text_sha256'):
            if not isinstance(d.get(key), str) or not d[key].strip():
                raise ValueError('Row %s: missing/non-string %s' % (i, key))
        if corpus_id and d['corpus_id'] != corpus_id:
            raise ValueError('Mixed corpus_id')
        identity = (d['corpus_id'], d['doc_id'])
        if identity in seen:
            raise ValueError('Duplicate document: ' + d['doc_id'])
        seen.add(identity)
        official_prefix = ('https://www.ey.gov.tw/File/43BC094940995CFC?A=C#page='
                           if d.get('document_type') == 'contract_rule'
                           else 'https://law.moj.gov.tw/')
        if not d['source_url'].startswith(official_prefix):
            raise ValueError('Unexpected official source')
        if hashlib.sha256(d['text'].encode('utf-8')).hexdigest() != d['text_sha256']:
            raise ValueError('Text hash mismatch: ' + d['doc_id'])
    if not records:
        raise ValueError('Empty corpus')
    return records

def load_corpus(path, corpus_id=None):
    rows = [json.loads(line) for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    return validate_records(rows, corpus_id)
