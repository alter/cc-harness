# test_push.py
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
from push import build_payload
from reminders import create_reminder


class Push(unittest.TestCase):
    def test_payload(self):
        db = []
        i = create_reminder(db, 7, "buy milk")
        self.assertEqual(build_payload(db[i])["title"], "Reminder")

    def test_user_id_bounds(self):
        with self.assertRaises(ValueError):
            create_reminder([], 0, "x")
