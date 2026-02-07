import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from video_source.match import best_fuzzy_match, exact_phrase_anchor
from video_source.types import CaptionSeg


class TestMatch(unittest.TestCase):
    def test_exact_phrase_anchor(self) -> None:
        segs = [
            CaptionSeg(0.0, 2.0, "People don't buy what you do"),
            CaptionSeg(2.0, 4.0, "they buy why you do it"),
        ]
        match = exact_phrase_anchor(segs, "People don't buy what you do, they buy why you do it.")
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.details.get("evidence"), "youtube:exact_phrase")

    def test_best_fuzzy_match(self) -> None:
        segs = [
            CaptionSeg(0.0, 1.5, "hello world this is a test"),
            CaptionSeg(1.5, 3.0, "from the unit tests suite"),
        ]
        match = best_fuzzy_match(segs, "hello world from unit tests", window_words=10, window_stride=2)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.details.get("evidence"), "youtube:timed_transcript")
        self.assertGreaterEqual(match.details.get("coverage", 0.0), 0.8)
