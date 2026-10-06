# test_retry.py
import unittest

from calc import fetch_with_retry


class Retry(unittest.TestCase):
    def test_retry_gives_up(self):
        self.assertIsNone(fetch_with_retry(lambda: None, retries=3, wait=1.0))
