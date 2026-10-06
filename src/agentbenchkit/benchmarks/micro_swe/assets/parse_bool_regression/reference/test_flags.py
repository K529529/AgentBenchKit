import unittest

from flags import parse_bool


class Regression(unittest.TestCase):
    def test_false_strings(self):
        for value in ("false", "no", "0", "off"):
            self.assertFalse(parse_bool(value))

    def test_invalid(self):
        with self.assertRaises(ValueError):
            parse_bool("unknown")
