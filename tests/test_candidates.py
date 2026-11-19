"""B: candidate phrases come from the PAT-tree and must map back to the original text."""
import unittest
from src.services import LawExploreService
from src.phrase_mining.candidates import mine, NUMBERING, CJK_ONLY
from src.phrase_mining.pat_tree import PATTreeIndex
from src.phrase_mining.reference import ReferencePhraseIndex


class CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = LawExploreService()
        cls.index = PATTreeIndex(cls.s.documents)
        cls.ref = ReferencePhraseIndex(cls.s.documents)
        cls.labour = mine(cls.s.documents, cls.index, domain='勞動')

    def test_found_without_seeds(self):
        phrases = {r['phrase'] for r in self.labour}
        for expected in ['工作時間', '延長工作時間', '勞動契約', '特別休假', '資遣費', '平均工資']:
            self.assertIn(expected, phrases)
        self.assertNotIn('作時間', phrases)        # 左邊永遠是「工」，不完整

    def test_counts_and_positions_match_scanner(self):
        for r in self.labour[:60]:
            ref = self.ref.lookup(r['phrase'])
            self.assertEqual(r['frequency'], ref['frequency'], r['phrase'])
            self.assertEqual(r['df'], ref['df'], r['phrase'])
            self.assertEqual(self.index.count(r['phrase']), ref['frequency'])
            for d, o in r['_occurrences']:
                self.assertEqual(self.index.texts[d][o:o + len(r['phrase'])], r['phrase'])

    def test_filters(self):
        for r in self.labour:
            self.assertTrue(CJK_ONLY.match(r['phrase']), r['phrase'])
            self.assertIsNone(NUMBERING.search(r['phrase']), r['phrase'])
            self.assertGreaterEqual(r['domain_df'], 2)
            self.assertGreaterEqual(r['se'], 0.3)

    def test_document_boundary(self):
        docs = [{'doc_id': 'a', 'domain': 'x', 'text': '甲乙丙勞動契約'},
                {'doc_id': 'b', 'domain': 'x', 'text': '終止勞動契約丁'},
                {'doc_id': 'c', 'domain': 'x', 'text': '依勞動契約。'}]
        rows = mine(docs, min_freq=2)
        self.assertIn('勞動契約', {r['phrase'] for r in rows})
        self.assertNotIn('約終', {r['phrase'] for r in rows})


if __name__ == '__main__':
    unittest.main()
