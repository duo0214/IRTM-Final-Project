"""B: 用 PAT-tree 從語料擷取候選詞組（不依賴種子詞）。

流程
----
1. PAT-tree 的每個內部節點都是「後面接的字不只一種」的重複字串，先全部列出來
   （頻率 ≥ min_freq、長度 min_len～max_len）。
2. 用下列規則過濾，每條規則都寫進輸出欄位，方便說明與檢討：
   * 只含中文字：去掉含標點、數字、空白的字串。
   * 文件數 df ≥ min_df：只在一份文件反覆出現的多半是該條的專屬寫法。
   * 左右都完整（maximal repeat）：左邊、右邊接的字都至少兩種；
     例如「作時間」左邊永遠是「工」，表示它是「工作時間」被切斷的片段。
   * 不是條號、日期、金額：含連續兩個以上中文數字，或「第＋數字」、
     「數字＋條項款章節年月日元萬」的字串（第三十二條、一百零五年…）是引用編號，不是概念詞。
   * 邊界不是虛詞：開頭或結尾是「之、及、或、的…」的字串多半是跨詞片段。
   * SE（Chien 1997 的 significance estimation）≥ min_se：
         SE(c) = f(c) / (f(a) + f(b) - f(c))，a、b 為 c 去尾字、去首字。
     SE 接近 1 表示 a、b 幾乎只以 c 的形式出現，c 是較完整的詞。
3. 依 score = SE × log2(1 + frequency) × min(左熵, 右熵, 1) 排序，
   指定 domain 時用該領域的出現次數。

可重跑：python -X utf8 -m src.phrase_mining.candidates --domain 勞動
"""
import argparse
import csv
import json
import math
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

from src.phrase_mining.pat_tree import PATTreeIndex

CJK_ONLY = re.compile(r'^[㐀-䶿一-鿿]+$')
# 不可作為詞組開頭／結尾的虛詞與連接字
BAD_START = set('之及或與並而且但的於其者所以為則即亦又如')
BAD_END = set('之及或與並而且但的於其所以為則即亦又如應得不由向對將自')
NUMERAL = '零〇一二三四五六七八九十百千萬'
NUMBERING = re.compile(r'[%s]{2,}|第[%s]|[%s][條項款目章節編年月日元萬]' % (NUMERAL, NUMERAL, NUMERAL))
START, END = '<s>', '</s>'


def entropy(counter):
    total = sum(counter.values())
    return -sum(v / total * math.log2(v / total) for v in counter.values()) if total else 0.0


def mine(documents, index=None, domain=None, min_freq=3, min_df=2, min_len=2, max_len=10,
         min_se=0.3, min_branch=2):
    index = index or PATTreeIndex(documents)
    texts = index.texts
    domains = [d['domain'] for d in documents]
    rows = []
    for phrase, freq, right, occurrences in index.repeated_strings(min_freq, min_len, max_len):
        if not CJK_ONLY.match(phrase):
            continue
        if NUMBERING.search(phrase):
            continue
        if phrase[0] in BAD_START or phrase[-1] in BAD_END:
            continue
        docs = {d for d, _ in occurrences}
        if len(docs) < min_df:
            continue
        left = Counter(texts[d][o - 1] if o > 0 else START for d, o in occurrences)
        right = Counter({(END if ch is None else ch): n for ch, n in right.items()})
        if len(left) < min_branch or len(right) < min_branch:
            continue
        se = freq / (index.count(phrase[:-1]) + index.count(phrase[1:]) - freq)
        if se < min_se:
            continue
        dom_freq = Counter(domains[d] for d, _ in occurrences)
        dom_df = Counter(domains[d] for d in docs)
        if domain and dom_df[domain] < min_df:
            continue
        le, re_ = entropy(left), entropy(right)
        f = dom_freq[domain] if domain else freq
        rows.append({
            'phrase': phrase, 'length': len(phrase), 'frequency': freq, 'df': len(docs),
            'domain_frequency': dom_freq[domain] if domain else '',
            'domain_df': dom_df[domain] if domain else '',
            'se': round(se, 4), 'left_branch': len(left), 'right_branch': len(right),
            'left_entropy': round(le, 4), 'right_entropy': round(re_, 4),
            'score': round(se * math.log2(1 + f) * min(le, re_, 1.0), 4),
            'domains': ';'.join('%s:%d' % kv for kv in sorted(dom_df.items(), key=lambda kv: -kv[1])),
            '_occurrences': occurrences,
        })
    rows.sort(key=lambda r: (-r['score'], -r['frequency'], r['phrase']))
    return rows


def write_outputs(rows, documents, out_dir, corpus_id, seeds=(), domain=None, top=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = rows[:top] if top else rows
    seeds = set(seeds)
    phrase_fields = ['corpus_id', 'rank', 'phrase', 'length', 'frequency', 'df', 'domain',
                     'domain_frequency', 'domain_df', 'se', 'left_branch', 'right_branch',
                     'left_entropy', 'right_entropy', 'score', 'is_seed', 'domains', 'method']
    doc_fields = ['corpus_id', 'phrase', 'doc_id', 'domain', 'law_name', 'article_no', 'tf', 'positions_json']
    with open(out_dir / 'phrases.csv', 'w', encoding='utf-8-sig', newline='') as fp:
        w = csv.DictWriter(fp, phrase_fields)
        w.writeheader()
        for rank, r in enumerate(rows, 1):
            w.writerow({**{k: r[k] for k in phrase_fields if k in r}, 'corpus_id': corpus_id,
                        'rank': rank, 'domain': domain or '', 'is_seed': int(r['phrase'] in seeds),
                        'method': 'pat_tree_maximal_repeat_se'})
    with open(out_dir / 'phrase_documents.csv', 'w', encoding='utf-8-sig', newline='') as fp:
        w = csv.DictWriter(fp, doc_fields)
        w.writeheader()
        for r in rows:
            by_doc = defaultdict(list)
            for d, o in r['_occurrences']:
                by_doc[d].append(o)
            for d in sorted(by_doc):
                doc = documents[d]
                starts = sorted(by_doc[d])
                w.writerow({'corpus_id': corpus_id, 'phrase': r['phrase'], 'doc_id': doc['doc_id'],
                            'domain': doc['domain'], 'law_name': doc['law_name'],
                            'article_no': doc['article_no'], 'tf': len(starts),
                            'positions_json': json.dumps([{'start': s, 'end': s + len(r['phrase'])}
                                                          for s in starts])})
    return len(rows)


def main():
    from src.services import LawExploreService
    ap = argparse.ArgumentParser(description='用 PAT-tree 擷取候選詞組')
    ap.add_argument('--domain', help='只輸出在此領域 df ≥ min-df 的詞組，例如 勞動')
    ap.add_argument('--min-freq', type=int, default=3)
    ap.add_argument('--min-df', type=int, default=2)
    ap.add_argument('--min-len', type=int, default=2)
    ap.add_argument('--max-len', type=int, default=10)
    ap.add_argument('--min-se', type=float, default=0.3)
    ap.add_argument('--top', type=int, help='只輸出前 N 名')
    ap.add_argument('--out', default='results/B')
    args = ap.parse_args()
    service = LawExploreService()
    t0 = time.perf_counter()
    rows = mine(service.documents, service.phrase_index if isinstance(service.phrase_index, PATTreeIndex) else None,
                args.domain, args.min_freq, args.min_df, args.min_len, args.max_len, args.min_se)
    elapsed = time.perf_counter() - t0
    n = write_outputs(rows, service.documents, args.out, service.corpus_id, service.phrases, args.domain, args.top)
    print('%d candidates (%s) in %.2fs -> %s/phrases.csv, phrase_documents.csv'
          % (n, args.domain or 'all domains', elapsed, args.out))
    for r in rows[:30]:
        print('  %-10s freq=%-4s df=%-3s se=%.2f score=%.2f' % (r['phrase'], r['frequency'], r['df'], r['se'], r['score']))


if __name__ == '__main__':
    main()
