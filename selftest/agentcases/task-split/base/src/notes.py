# notes.py


class Notes:
    def __init__(self, db):
        self.db = db

    def add(self, text):
        raise NotImplementedError

    def list(self):
        raise NotImplementedError
