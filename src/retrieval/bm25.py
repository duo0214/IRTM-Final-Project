"""C's runnable reference baseline: character unigram+bigram BM25, no synonym inference."""
import math
import re
import unicodedata
from collections import Counter

def tokenize(text):
    normalized = unicodedata.normalize('NFKC', text).lower()
    tokens = []
    for segment in re.findall(r'[\u3400-\u9fff]+|[a-z0-9]+', normalized):
        if re.fullmatch('[a-z0-9]+', segment):
            tokens.append(segment)
        else:
            tokens.extend(segment)
            tokens.extend(segment[i:i+2] for i in range(len(segment)-1))
    return tokens

class BM25Baseline:
    backend = 'character_bigram_bm25_baseline'

    def __init__(self, documents, k1=1.5, b=0.75):
        self.documents = documents
        self.k1, self.b = k1, b
        self.counts = [Counter(tokenize(d['text'])) for d in documents]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.avgdl = sum(self.lengths) / max(1, len(documents)) or 1
        self.df = Counter(t for c in self.counts for t in c)

    def search(self, query, top_k=5, domain=None):
        terms = set(tokenize(query))
        rows = []
        n = len(self.documents)
        for doc, counts, length in zip(self.documents, self.counts, self.lengths):
            if domain and doc['domain'] != domain:
                continue
            score = 0.0
            for term in terms:
                tf = counts.get(term, 0)
                if tf:
                    idf = math.log(1 + (n-self.df[term]+0.5)/(self.df[term]+0.5))
                    score += idf * tf * (self.k1+1) / (tf+self.k1*(1-self.b+self.b*length/self.avgdl))
            if score > 0:
                rows.append({'doc_id': doc['doc_id'], 'score': round(score, 6)})
        return sorted(rows, key=lambda d: (-d['score'], d['doc_id']))[:top_k]
