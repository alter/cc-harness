# test_body.py
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from parser import Parser


class Body(unittest.TestCase):
    def test_body(self):
        self.assertEqual(Parser("A: 1\n\nhello\nworld").body(), "hello\nworld")
