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
    def test_true(self):
        for value in [True, "true", "YES", " 1 ", "on"]:
            self.assertIs(load("flags").parse_bool(value), True)

    def test_false(self):
        for value in [False, "false", "NO", " 0 ", "off"]:
            self.assertIs(load("flags").parse_bool(value), False)

    def test_invalid(self):
        for value in [None, 1, [], "unknown", ""]:
            with self.assertRaises(ValueError):
                load("flags").parse_bool(value)

    def test_regression_present(self):
        self.assertTrue((workspace / "test_flags.py").is_file())

    def test_regression_runs(self):
        suite = unittest.defaultTestLoader.loadTestsFromModule(load("test_flags"))
        result = unittest.TestResult()
        suite.run(result)
        self.assertGreaterEqual(result.testsRun, 2)
        self.assertTrue(result.wasSuccessful())


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
