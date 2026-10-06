# test_math_again.py
import unittest

from calc import add


class AddAgain(unittest.TestCase):
    def test_add_again(self):
        self.assertEqual(add(2, 3), 5)
