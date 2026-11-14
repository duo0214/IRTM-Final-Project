import copy
import math
import unittest
from src.services import LawExploreService, ServiceError, ROOT
from src.corpus.validation import validate_records
from src.corpus.parser import parse_official, parse_rental_rules
from src.phrase_mining.reference import ReferencePhraseIndex, positions
from src.retrieval.bm25 import BM25Baseline
from src.evaluation.metrics import evaluate
import json

class CorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.s=LawExploreService()

    def test_source_roundtrip(self):
        scopes=json.loads((ROOT/'config/scope.json').read_text(encoding='utf-8'))
        manifest=json.loads((ROOT/'data/seed/source_manifest.json').read_text(encoding='utf-8'))
        parsed=parse_official(ROOT/'data/seed/official_sample.xml',scopes,self.s.corpus_id,manifest['retrieved_at'])
        self.assertEqual(sum(len(s["articles"]) for s in scopes),len(parsed))
        source=manifest['rental_rules']
        rules=parse_rental_rules(ROOT/source['points_file'],source,self.s.corpus_id)
        self.assertEqual(sorted(parsed+rules,key=lambda doc: doc['doc_id']),self.s.documents)
        power_rule=self.s.by_id['moi_residential_lease_required_6']
        self.assertIn('當期每度平均電價',power_rule['text'])
        result=self.s.search('不得遷入戶籍',5,'租賃')
        self.assertIn('moi_residential_lease_prohibited_4',{doc['doc_id'] for doc in result['results']})
        self.assertGreater(len(parsed),400)
        self.assertIn("moj_B0000001_463-1",self.s.by_id)
        self.assertTrue(all(d["text"].strip() not in ("（刪除）", "(刪除)") for d in parsed))

    def test_tamper_duplicate_and_cross_corpus(self):
        bad=copy.deepcopy(self.s.documents);bad[0]['text']+='x'
        with self.assertRaises(ValueError):validate_records(bad)
        with self.assertRaises(ValueError):validate_records(self.s.documents*2)
        with self.assertRaises(ValueError):validate_records(self.s.documents,'benchmark_v1')
        with self.assertRaises(ServiceError):self.s.check_corpus('benchmark_v1')

    def test_phrase_invariants_and_context(self):
        for phrase in self.s.phrases:
            result=self.s.phrase(phrase)
            self.assertEqual(result['frequency'],sum(d['tf'] for d in result['documents']))
            self.assertEqual(result['df'],len(result['documents']))
            for d in result['documents']:
                for p in d['positions']:
                    self.assertEqual(self.s.by_id[d['doc_id']]['text'][p['start']:p['end']],phrase)
                for c in d['contexts']:
                    self.assertEqual(c['text'][c['match_start']:c['match_end']],phrase)

    def test_literal_overlap_unicode_and_boundaries(self):
        self.assertEqual(positions('哈哈哈','哈哈'),[{'start':0,'end':2},{'start':1,'end':3}])
        self.assertEqual(positions('😀修繕','修繕'),[{'start':1,'end':3}])
        index=ReferencePhraseIndex([{'doc_id':'a','text':'出租'},{'doc_id':'b','text':'人'}])
        self.assertEqual(index.lookup('出租人')['frequency'],0)
        self.assertEqual(index.lookup('不存在')['df'],0)

    def test_search_determinism_and_domain(self):
        a=self.s.search('工資',5,'勞動')
        self.assertEqual(a,self.s.search('工資',5,'勞動'))
        self.assertTrue(a['results'])
        self.assertTrue(all(d['domain']=='勞動' for d in a['results']))
        self.assertEqual(self.s.search('zzzzzzzzz')['results'],[])
        for query in ('',' '*5,'x'*201):
            with self.assertRaises(ServiceError):self.s.search(query)
        with self.assertRaises(ServiceError):self.s.search('工資',0)

    def test_bm25_known_score_and_ties(self):
        docs=[{'doc_id':'b','text':'a','domain':'x'},{'doc_id':'a','text':'a','domain':'x'}]
        ranked=BM25Baseline(docs).search('a')
        self.assertEqual([d['doc_id'] for d in ranked],['a','b'])
        self.assertAlmostEqual(ranked[0]['score'],math.log(1+0.5/2.5),places=5)

    def test_suggestions_and_jaccard_have_evidence(self):
        for s in self.s.search('出租人')['suggestions']:
            self.assertTrue(s['source_doc_ids'])
            for doc_id in s['source_doc_ids']:self.assertIn(s['phrase'],self.s.by_id[doc_id]['text'])
        for r in self.s.phrase('修繕')['related_terms']:
            a={d['doc_id'] for d in self.s.phrase_index.lookup('修繕')['documents']}
            b={d['doc_id'] for d in self.s.phrase_index.lookup(r['phrase'])['documents']}
            self.assertEqual(r['score'],len(a&b)/len(a|b))

class MetricTests(unittest.TestCase):
    def test_hand_calculated(self):
        m=evaluate({'q':['x','a','b']},{'q':{'a':2,'b':1}})['metrics']
        self.assertEqual(m['MRR@10'],.5);self.assertEqual(m['Recall@5'],1)
        self.assertAlmostEqual(m['nDCG@10'],(3/math.log2(3)+1/math.log2(4))/(3+1/math.log2(3)))

    def test_missing_run_is_zero_and_invalid_judgments_fail(self):
        self.assertEqual(evaluate({}, {'q':{'a':1}})['metrics']['MRR@10'],0)
        with self.assertRaises(ValueError):evaluate({'q':['a','a']},{'q':{'a':1}})
        with self.assertRaises(ValueError):evaluate({}, {'q':{'a':0}})
        with self.assertRaises(ValueError):evaluate({'unknown':[]},{'q':{'a':1}})

if __name__=='__main__':unittest.main()
