import csv
import tempfile
import unittest
from pathlib import Path
from src.corpus.annotations import validate_annotations, FIELDS

class AnnotationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.docs=[{'doc_id':'d','text':'出租人修繕'}];self.rows=[]
    def tearDown(self):self.tmp.cleanup()
    def write(self,kind,row):
        record=dict.fromkeys(FIELDS,'')
        record.update(kind={'qrels':'qrel','queries':'query','phrases':'phrase'}[kind],id='A_'+str(len(self.rows)),corpus_id=row['corpus_id'],doc_id=row.get('doc_id',''),query_id=row.get('query_id',''),text=row.get('query',row.get('phrase','')),label=row.get('relevance',row.get('split',row.get('label',''))),evidence=row.get('evidence','test'),author=row.get('annotator',row.get('author','')),status=row['review_status'])
        if kind=='queries':record['id']=row['query_id']
        self.rows.append(record)
        with (self.root/'A.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(self.rows)
    def test_empty_is_not_completed(self):
        self.assertEqual(validate_annotations(self.root,self.docs,'c')['rows_checked'],0)
    def test_invalid_cross_references_fail(self):
        self.write('qrels',dict(corpus_id='wrong',query_id='A_001',doc_id='missing',relevance='3',annotator='A',review_status='approved',evidence='x'))
        with self.assertRaises(ValueError) as caught:validate_annotations(self.root,self.docs,'c')
        self.assertIn('wrong corpus_id',str(caught.exception));self.assertIn('unknown query_id',str(caught.exception))
    def test_role_can_confirm_its_own_query_and_judgment(self):
        self.write('queries',dict(corpus_id='c',query_id='A_001',query='修繕由誰負擔',author='A',review_status='approved',split='demo'))
        self.write('qrels',dict(corpus_id='c',query_id='A_001',doc_id='d',relevance='2',annotator='A',review_status='approved',evidence='核對文本'))
        result = validate_annotations(self.root, self.docs, 'c')
        self.assertEqual(result['judgments'], 1)
        self.assertEqual(result['approved_rows'], 2)
    def test_phrase_must_exist(self):
        self.write('phrases',dict(corpus_id='c',doc_id='d',phrase='不存在',label='valid',annotator='A',review_status='draft'))
        with self.assertRaises(ValueError):validate_annotations(self.root,self.docs,'c')
