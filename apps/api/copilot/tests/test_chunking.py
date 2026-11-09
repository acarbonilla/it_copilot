from django.test import SimpleTestCase

from copilot.chunking import chunk_text, count_tokens
from copilot.retrieval import InvalidQuestion, normalize_question


class ChunkingTests(SimpleTestCase):
    def test_empty_and_whitespace_are_empty(self):
        self.assertEqual(chunk_text(""), ())
        self.assertEqual(chunk_text(" \n\t"), ())

    def test_unicode_is_deterministic_and_accounted(self):
        text = "Résumé 東京 support.\n\nSecond paragraph — resolved."
        first = chunk_text(text, max_tokens=6, overlap_tokens=2)
        self.assertEqual(first, chunk_text(text, max_tokens=6, overlap_tokens=2))
        self.assertTrue(all(item.token_count <= 6 for item in first))
        self.assertEqual(first[0].token_count, count_tokens(first[0].text))

    def test_long_input_overlap_and_digest(self):
        chunks = chunk_text(" ".join(f"token{i}" for i in range(50)), max_tokens=10, overlap_tokens=2)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0].text.split()[-2:], chunks[1].text.split()[:2])
        self.assertEqual([item.ordinal for item in chunks], list(range(len(chunks))))

    def test_question_normalization_and_limit(self):
        self.assertEqual(normalize_question("  reset\n password "), "reset password")
        with self.assertRaises(InvalidQuestion):
            normalize_question(" ")
        with self.assertRaises(InvalidQuestion):
            normalize_question("x" * 2001)
