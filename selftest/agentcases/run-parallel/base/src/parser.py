# parser.py


class Parser:
    def __init__(self, text):
        self.lines = text.split("\n")

    def headers(self):
        raise NotImplementedError

    def _separator(self):
        for i, line in enumerate(self.lines):
            if line == "":
                return i
        return len(self.lines)

    def _unused_padding_one(self):
        return None

    def _unused_padding_two(self):
        return None

    def body(self):
        raise NotImplementedError
