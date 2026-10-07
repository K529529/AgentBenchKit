import importlib.util
import json
import sys
import unittest
from pathlib import Path

workspace = Path(sys.argv[1])
report_path = Path(sys.argv[2])
sys.path.insert(0, str(workspace))


def load(name):
    spec = importlib.util.spec_from_file_location(name, workspace / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Checks(unittest.TestCase):
    def test_nested(self):
        self.assertEqual(load("lookup").dotted_get({"a": {"b": 3}}, "a.b"), 3)

    def test_missing(self):
        self.assertEqual(load("lookup").dotted_get({}, "a.b", 99), 99)

    def test_non_dict(self):
        self.assertEqual(load("lookup").dotted_get({"a": 2}, "a.b", 99), 99)

    def test_falsey(self):
        for value in [False, 0, "", None]:
            self.assertEqual(load("lookup").dotted_get({"a": value}, "a", 99), value)

    def test_empty_path(self):
        value = {"a": 1}
        self.assertIs(load("lookup").dotted_get(value, ""), value)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    )
    report_path.write_text(
        json.dumps(
            {
                "executed": result.testsRun,
                "failed": len(result.failures) + len(result.errors),
                "skipped": len(result.skipped),
            }
        ),
        encoding="utf-8",
    )
    raise SystemExit(0 if result.wasSuccessful() else 1)
