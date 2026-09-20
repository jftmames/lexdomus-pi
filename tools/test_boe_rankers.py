"""Arithmetic, abstention and passage-coverage checks for offline diagnostics."""
import math
import unittest
from tools.compare_boe_rankers import covered, rank


class RankerTests(unittest.TestCase):
    def test_hand_calculated_single_document_score(self):
        # N=df=1, length=average, f=2: idf=ln(4/3), TF=4.4/3.2.
        score, index = rank(['plazo plazo'], 'plazo', 'bm25')[0]
        self.assertEqual(index, 0)
        self.assertAlmostEqual(score, math.log(4 / 3) * 4.4 / 3.2)

    def test_absent_tokens_and_empty_inputs(self):
        for mode in ('lexical', 'bm25'):
            self.assertEqual(rank(['plazo'], 'tributo', mode), [])
            self.assertEqual(rank(['plazo'], '', mode), [])
            self.assertEqual(rank([], 'plazo', mode), [])
            self.assertEqual(rank([''], 'plazo', mode), [])

    def test_ties_and_top_k_are_stable(self):
        for mode in ('lexical', 'bm25'):
            self.assertEqual([i for _, i in rank(['plazo'] * 8, 'plazo', mode)], list(range(6)))

    def test_gap_and_wrong_article_cannot_satisfy_passage(self):
        parts = [{'article': '43', 'char_start': 0, 'char_end': 40},
                 {'article': '43', 'char_start': 41, 'char_end': 100},
                 {'article': '45', 'char_start': 0, 'char_end': 100}]
        self.assertFalse(covered(parts, '43', 0, 100))
        parts.append({'article': '43', 'char_start': 39, 'char_end': 42})
        self.assertTrue(covered(parts, '43', 0, 100))


if __name__ == '__main__':
    unittest.main()
