from __future__ import annotations

import unittest

from paper_translator.text_utils import normalize_markdown, slugify_title, strip_code_fences


class TextUtilsTest(unittest.TestCase):
    def test_slugify_title(self) -> None:
        self.assertEqual(slugify_title("Attention Is All You Need"), "attention-is-all-you-need")

    def test_strip_code_fences(self) -> None:
        self.assertEqual(strip_code_fences("```json\n{\"a\":1}\n```"), "{\"a\":1}")

    def test_normalize_markdown(self) -> None:
        value = normalize_markdown("A  \n\n\nB\r\n")
        self.assertEqual(value, "A\n\nB\n")


if __name__ == "__main__":
    unittest.main()

