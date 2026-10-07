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
    def test_empty(self):
        self.assertEqual(load("intervals").merge_intervals([]), [])

    def test_touching(self):
        self.assertEqual(load("intervals").merge_intervals([(3, 5), (1, 3)]), [(1, 5)])

    def test_nested(self):
        self.assertEqual(
            load("intervals").merge_intervals([(1, 8), (2, 3), (9, 9)]), [(1, 8), (9, 9)]
        )

    def test_reversed(self):
        with self.assertRaises(ValueError):
            load("intervals").merge_intervals([(4, 2)])

    def test_input_unchanged(self):
        items = [(5, 6), (1, 2)]
        load("intervals").merge_intervals(items)
        self.assertEqual(items, [(5, 6), (1, 2)])


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
