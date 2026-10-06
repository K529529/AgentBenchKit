import importlib.util
import json
import sys
import unittest
from pathlib import Path

workspace = Path(sys.argv[1])
report_path = Path(sys.argv[2])


def load(name):
    spec = importlib.util.spec_from_file_location(name, workspace / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Checks(unittest.TestCase):
    def test_order(self):
        self.assertEqual(load("sequence_tools").stable_unique([3, 1, 3, 2, 1]), [3, 1, 2])

    def test_empty(self):
        self.assertEqual(load("sequence_tools").stable_unique([]), [])

    def test_generator(self):
        self.assertEqual(load("sequence_tools").stable_unique(x for x in [2, 2, 1]), [2, 1])

    def test_input_unchanged(self):
        original = [1, 1, 2]
        self.assertEqual(load("sequence_tools").stable_unique(original), [1, 2])
        self.assertEqual(original, [1, 1, 2])

    def test_strings(self):
        self.assertEqual(load("sequence_tools").stable_unique(["b", "a", "b"]), ["b", "a"])


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
