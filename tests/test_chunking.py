"""Chunk coordinates must reconstruct the complete normalized source."""

import unittest

from lex_domus.chunking import normalize_text, split_text


class ChunkingTests(unittest.TestCase):
    def assert_lossless(self, raw, *, max_chars=1000, overlap_chars=120):
        normalized = normalize_text(raw)
        chunks = split_text(raw, max_chars=max_chars, overlap_chars=overlap_chars)
        reconstructed = ""
        previous_end = 0
        previous_start = -1
        for index, chunk in enumerate(chunks):
            start, end = chunk["char_start"], chunk["char_end"]
            self.assertGreater(start, previous_start)
            self.assertLessEqual(start, previous_end)
            self.assertGreater(end, previous_end)
            self.assertLessEqual(end, len(normalized))
            self.assertLessEqual(end - start, max_chars)
            self.assertEqual(chunk["text"], normalized[start:end])
            self.assertEqual(chunk["line_start"], normalized[:start].count("\n") + 1)
            self.assertEqual(chunk["line_end"], normalized[:end - 1].count("\n") + 1)
            if index:
                self.assertEqual(previous_end - start, overlap_chars)
            reconstructed += chunk["text"][previous_end - start:]
            previous_start, previous_end = start, end
        self.assertEqual(reconstructed, normalized)
        self.assertEqual(previous_end, len(normalized))
        return chunks

    def test_normalization_preserves_bom_and_all_whitespace(self):
        raw = "\ufeff \t\r\n\runo  \r\ndos\t \r\n\r\n \t"
        expected = "\ufeff \t\n\nuno  \ndos\t \n\n \t"
        self.assertEqual(normalize_text(raw), expected)
        self.assertEqual(normalize_text(expected), expected)
        self.assert_lossless(raw, max_chars=7, overlap_chars=3)

    def test_a_long_unbroken_line_is_fully_retained(self):
        text = "x" * 3457
        chunks = self.assert_lossless(text)
        self.assertEqual(len(chunks), 4)
        self.assertEqual([chunk["char_start"] for chunk in chunks], [0, 880, 1760, 2640])
        self.assertTrue(all(chunk["line_start"] == chunk["line_end"] == 1 for chunk in chunks))

    def test_unicode_offsets_are_code_points_not_encoded_bytes(self):
        text = "Á🙂e\u0301\nñ🚀fin"
        chunks = self.assert_lossless(text, max_chars=4, overlap_chars=1)
        self.assertEqual(chunks[0]["text"], "Á🙂e\u0301")
        self.assertEqual(chunks[0]["char_end"], 4)
        self.assertEqual(chunks[1]["text"], "\u0301\nñ🚀")

    def test_blank_only_sources_are_not_discarded(self):
        for text in (" ", "\t\t", "\n", "\n\n", " \r\n\r\n\t "):
            with self.subTest(text=text):
                self.assert_lossless(text, max_chars=2, overlap_chars=1)

    def test_newline_at_end_of_window_belongs_to_preceding_line(self):
        chunks = self.assert_lossless("a\nb\n", max_chars=2, overlap_chars=0)
        self.assertEqual([(c["line_start"], c["line_end"]) for c in chunks], [(1, 1), (2, 2)])
        chunks = self.assert_lossless("\n\nx", max_chars=1, overlap_chars=0)
        self.assertEqual([(c["line_start"], c["line_end"]) for c in chunks], [(1, 1), (2, 2), (3, 3)])

    def test_overlapping_window_can_begin_on_newline(self):
        chunks = self.assert_lossless("ab\ncd\nef", max_chars=4, overlap_chars=2)
        self.assertEqual(chunks[1]["char_start"], 2)
        self.assertEqual(chunks[1]["text"], "\ncd\n")
        self.assertEqual((chunks[1]["line_start"], chunks[1]["line_end"]), (1, 2))

    def test_empty_input_returns_no_chunks(self):
        self.assertEqual(self.assert_lossless(""), [])

    def test_extreme_overlap_still_makes_progress_without_redundant_tail(self):
        chunks = self.assert_lossless("0123456789", max_chars=4, overlap_chars=3)
        self.assertEqual([c["char_start"] for c in chunks], list(range(7)))
        self.assertEqual(chunks[-1]["text"], "6789")

    def test_short_and_exact_size_inputs_need_only_one_window(self):
        for length in (1, 119, 120, 121, 999, 1000):
            with self.subTest(length=length):
                chunks = self.assert_lossless(" " * length)
                self.assertEqual(len(chunks), 1)

    def test_many_window_sizes_and_overlaps_reconstruct_deterministically(self):
        text = " \r\ná🙂\t\n\nfin \r" * 15
        for maximum in (1, 2, 3, 7, 20, 1000):
            for overlap in sorted({0, maximum // 2, maximum - 1}):
                with self.subTest(max_chars=maximum, overlap_chars=overlap):
                    chunks = self.assert_lossless(text, max_chars=maximum, overlap_chars=overlap)
                    self.assertEqual(chunks, split_text(text, max_chars=maximum, overlap_chars=overlap))

    def test_invalid_window_arguments_are_rejected_even_for_empty_input(self):
        for name in ("max_chars", "overlap_chars"):
            for value in (True, False, 1.0, "1", None):
                with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                    split_text("", **{name: value})
        for kwargs in ({"max_chars": 0}, {"max_chars": -1}, {"overlap_chars": -1},
                       {"overlap_chars": 1000}, {"overlap_chars": 1001},
                       {"max_chars": 120}, {"max_chars": 3, "overlap_chars": 3}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                split_text("", **kwargs)

    def test_non_string_sources_are_rejected(self):
        for value in (None, b"text", 123, ["text"]):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    normalize_text(value)
                with self.assertRaises(TypeError):
                    split_text(value)


if __name__ == "__main__":
    unittest.main()
