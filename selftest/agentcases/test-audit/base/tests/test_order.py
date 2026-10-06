# test_order.py
import pathlib
import unittest

STATE = pathlib.Path("state.txt")


class Order(unittest.TestCase):
    def test_1_save(self):
        STATE.write_text("saved")
        self.assertTrue(STATE.exists())

    def test_2_load(self):
        self.assertEqual(STATE.read_text(), "saved")
