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
        self.assertEqual(load("chunks").chunked([], 2), [])

    def test_remainder(self):
        self.assertEqual(load("chunks").chunked([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])

    def test_generator(self):
        self.assertEqual(load("chunks").chunked((i for i in range(3)), 2), [[0, 1], [2]])

    def test_invalid(self):
        for size in [0, -1, True, 1.5]:
            with self.assertRaises(ValueError):
                load("chunks").chunked([], size)

    def test_unchanged(self):
        source = [1, 2, 3]
        load("chunks").chunked(source, 1)
        self.assertEqual(source, [1, 2, 3])


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
