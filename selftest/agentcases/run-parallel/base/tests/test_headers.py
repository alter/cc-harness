# test_headers.py
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from parser import Parser


class Headers(unittest.TestCase):
    def test_headers(self):
        self.assertEqual(Parser("A: 1\nB: 2\n\nhello").headers(), {"A": "1", "B": "2"})
