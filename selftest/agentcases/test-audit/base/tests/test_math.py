# test_math.py
import unittest

from calc import add


class Add(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)
