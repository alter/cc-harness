# test_rates.py
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
from rates import store_rate


class FakeClient:
    def get_rate(self, currency):
        return 1.25


class StoreRate(unittest.TestCase):
    def test_rate_is_stored(self):
        path = os.path.join(tempfile.mkdtemp(), "r.db")
        self.assertEqual(store_rate(path, FakeClient(), "EUR"), 1.25)
        rows = sqlite3.connect(path).execute("SELECT currency, rate FROM rates").fetchall()
        self.assertEqual(rows, [("EUR", 1.25)])


if __name__ == "__main__":
    unittest.main()
