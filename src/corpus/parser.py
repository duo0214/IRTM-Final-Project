"""A owns this minimal, real official XML parser. Preserve source text for offsets."""
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlparse

PARSER_VERSION = 'official-xml-starter-1'

def article_key(value):
    match = re.fullmatch(r'第\s*(\d+(?:-\d+)?)\s*條', value.strip())
    if not match:
        raise ValueError('Unrecognized article number: ' + value)
    return match.group(1)

def parse_official(path, scopes, corpus_id, retrieved_at):
    root = ET.parse(path).getroot()
    wanted = {s['law_id']: s for s in scopes}
    records = []
    for law in root.findall('法規'):
        url = law.findtext('法規網址', '').strip()
        params = {k.lower(): v for k, v in parse_qs(urlparse(url).query).items()}
        law_id = params.get('pcode', [''])[0]
        if law_id not in wanted:
            continue
        scope = wanted[law_id]
        for article in law.findall('./法規內容/條文'):
            number = article.findtext('條號', '').strip()
            key = article_key(number)
            if key not in scope['articles']:
                continue
            # XML parser normalizes CRLF to LF. No NFKC, whitespace deletion or paraphrase.
            text = article.findtext('條文內容', '')
            records.append({
                'schema_version': '1.0', 'corpus_id': corpus_id,
                'doc_id': 'moj_' + law_id + '_' + key,
                'law_id': law_id, 'law_name': law.findtext('法規名稱', '').strip(),
                'article_no': number, 'article_key': key, 'text': text,
                'domain': scope['domain'], 'source_url': url,
                'retrieved_at': retrieved_at,
                'law_version_date': law.findtext('最新異動日期', '').strip() or None,
                'effective_date_raw': law.findtext('生效日期', '').strip() or None,
                'effective_note': law.findtext('生效內容', '').strip() or None,
                'effective_status': 'not_individually_verified',
                'source_update_raw': root.get('UpdateDate'),
                'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                'parser_version': PARSER_VERSION,
            })
    expected = sum(len(s['articles']) for s in scopes)
    if len(records) != expected:
        raise ValueError('Expected %s selected articles, found %s' % (expected, len(records)))
    return sorted(records, key=lambda d: d['doc_id'])

def write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(d, ensure_ascii=False) + '\n' for d in records), encoding='utf-8')


def parse_rental_rules(path, source, corpus_id):
    """Load the numbered points transcribed from the official notice PDF."""
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != source['points_sha256']:
        raise ValueError('Rental rules source hash mismatch')
    points = json.loads(payload)
    expected = [(section, number) for section, count in [('required', 23), ('prohibited', 10)]
                for number in range(1, count + 1)]
    if [(point['section'], point['number']) for point in points] != expected:
        raise ValueError('Rental rules source has missing, duplicate or unexpected points')
    records = []
    for point in points:
        key = '{}_{}'.format(point['section'], point['number'])
        section = {'required': '應記載', 'prohibited': '不得記載'}[point['section']]
        text = point['text']
        records.append({
            'schema_version': '1.0', 'corpus_id': corpus_id,
            'doc_id': 'moi_residential_lease_' + key,
            'law_id': 'moi_residential_lease', 'law_name': source['title'],
            'article_no': '{}第 {} 點'.format(section, point['number']),
            'article_key': key, 'text': text, 'domain': '租賃',
            'source_url': source['pdf_url'] + '#page=' + str(point['page']),
            'document_type': 'contract_rule',
            'retrieved_at': source['retrieved_at'], 'law_version_date': source['version_date'],
            'effective_date_raw': None, 'effective_note': source['effective_note'],
            'effective_status': 'not_individually_verified', 'source_update_raw': None,
            'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'parser_version': 'rental-rules-pdf-points-1',
        })
    return records
