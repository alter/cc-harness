# test_smoke.py
import unittest

from app import billing


class Smoke(unittest.TestCase):
    def test_currency_is_set(self):
        self.assertTrue(billing.CURRENCY)


if __name__ == "__main__":
    unittest.main()
