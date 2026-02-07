import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from video_source.util import extract_youtube_id, normalize_text


class TestUtil(unittest.TestCase):
    def test_extract_youtube_id(self) -> None:
        vid = "qp0HIF3SfI4"
        self.assertEqual(extract_youtube_id(vid), vid)
        self.assertEqual(extract_youtube_id(f"https://www.youtube.com/watch?v={vid}"), vid)
        self.assertEqual(extract_youtube_id(f"https://youtu.be/{vid}"), vid)
        self.assertEqual(extract_youtube_id(f"https://www.youtube.com/shorts/{vid}"), vid)
        self.assertIsNone(extract_youtube_id("https://example.com"))

    def test_normalize_text(self) -> None:
        self.assertEqual(normalize_text("Hello, world!"), "hello world")
        self.assertEqual(normalize_text("A  b\tc"), "a b c")
