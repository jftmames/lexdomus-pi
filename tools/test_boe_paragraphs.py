import unittest
from tools.compare_boe_paragraphs import paragraph_chunks


class ParagraphTests(unittest.TestCase):
    def test_exact_reconstruction_and_boundaries(self):
        text = 'Título\n\n' + 'a' * 700 + '\n\n' + 'b' * 450 + '\n\nFinal'
        chunks = paragraph_chunks(text)
        self.assertEqual(''.join(c['text'] for c in chunks), text)
        self.assertTrue(all(c['text'] == text[c['char_start']:c['char_end']] for c in chunks))
        self.assertTrue(any('b' * 450 in c['text'] for c in chunks))
        self.assertEqual(chunks[-1]['char_end'], len(text))

    def test_oversized_paragraph_is_not_silently_cut(self):
        text = 'Título\n\n' + 'x' * 1400 + '\n\nFinal'
        chunks = paragraph_chunks(text)
        self.assertTrue(any('x' * 1400 in c['text'] for c in chunks))
        self.assertEqual(''.join(c['text'] for c in chunks), text)

    def test_empty_and_invalid_target(self):
        self.assertEqual(paragraph_chunks(''), [])
        for target in (0, -1, True):
            with self.assertRaises(ValueError):
                paragraph_chunks('x', target)
