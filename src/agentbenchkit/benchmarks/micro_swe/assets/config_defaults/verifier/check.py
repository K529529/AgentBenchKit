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
    def test_defaults(self):
        self.assertEqual(
            load("settings").load_settings(workspace / "defaults.toml"),
            {"timeout": 30, "retries": 2},
        )

    def test_override(self):
        self.assertEqual(
            load("settings").load_settings(workspace / "defaults.toml", {"timeout": 5})["timeout"],
            5,
        )

    def test_falsey(self):
        self.assertEqual(
            load("settings").load_settings(workspace / "defaults.toml", {"retries": 0})["retries"],
            0,
        )

    def test_no_mutation(self):
        source = {"timeout": 2}
        load("settings").load_settings(workspace / "defaults.toml", source)
        self.assertEqual(source, {"timeout": 2})

    def test_file_values(self):
        import tomllib

        self.assertEqual(tomllib.loads((workspace / "defaults.toml").read_text())["timeout"], 30)


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
