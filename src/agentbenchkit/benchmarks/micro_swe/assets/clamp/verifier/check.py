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
    def test_inside(self):
        self.assertEqual(load("bounds").clamp(5, 0, 10), 5)

    def test_below(self):
        self.assertEqual(load("bounds").clamp(-5, 0, 10), 0)

    def test_above(self):
        self.assertEqual(load("bounds").clamp(15, 0, 10), 10)

    def test_equal_bounds(self):
        self.assertEqual(load("bounds").clamp(5, 3, 3), 3)

    def test_invalid_bounds(self):
        with self.assertRaises(ValueError):
            load("bounds").clamp(5, 10, 0)


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
