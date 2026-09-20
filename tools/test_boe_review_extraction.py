"""Regression checks for omitted substantive BOE paragraphs; no source approval."""
import copy
import json
import unittest
from pathlib import Path
from tools.extract_boe_review import extract

CAPTURE = Path(__file__).resolve().parents[1] / 'docs/T04-evidence/boe-dom-capture.json'


class BoeReviewExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.capture = json.loads(CAPTURE.read_text())
        cls.articles = {a['article']: a for a in extract(cls.capture)}

    def test_previously_missing_substantive_provisions_are_preserved(self):
        expectations = {
            '14': ['1.º Decidir si su obra ha de ser divulgada y en qué forma.',
                   'Este derecho no permitirá exigir el desplazamiento de la obra'],
            '60': ['1.º Si la cesión del autor al editor tiene carácter de exclusiva.'],
            '62': ['a) La lengua o lenguas en que ha de publicarse la obra.',
                   '2. La falta de expresión de la lengua o lenguas'],
        }
        for article, passages in expectations.items():
            for passage in passages:
                with self.subTest(article=article, passage=passage):
                    self.assertIn(passage, self.articles[article]['text'])

    def test_notes_and_repeal_are_not_lost_or_mixed(self):
        self.assertEqual(len(self.articles), 40)
        self.assertTrue(self.articles['54']['repealed_marker'])
        self.assertNotIn('Se añade', self.articles['48 bis']['text'])
        self.assertTrue(any('Se añade' in n for n in self.articles['48 bis']['notes']))

    def test_unknown_markup_blocks_silent_omission(self):
        for markup in ['<p class="new-format">Texto nuevo</p>', '<section>Texto nuevo</section>']:
            capture = copy.deepcopy(self.capture)
            capture['blocks'][0]['html'] = capture['blocks'][0]['html'].replace('</div>', markup + '</div>')
            with self.subTest(markup=markup), self.assertRaises(ValueError):
                extract(capture)


if __name__ == '__main__':
    unittest.main()
