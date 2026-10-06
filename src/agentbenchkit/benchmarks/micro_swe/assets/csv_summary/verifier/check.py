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
    def test_parse_types(self):
        self.assertEqual(
            load("parsing").parse_rows("item,quantity,price\na,2,1.5\n"),
            [{"item": "a", "quantity": 2, "price": 1.5}],
        )

    def test_quoted(self):
        self.assertEqual(
            load("parsing").parse_rows('item,quantity,price\n"a,b",2,3\n')[0]["item"], "a,b"
        )

    def test_repeated(self):
        self.assertEqual(
            load("reporting").totals("item,quantity,price\na,2,1.5\na,3,2\n"), {"a": 9.0}
        )

    def test_empty(self):
        self.assertEqual(load("reporting").totals("item,quantity,price\n"), {})

    def test_multiple(self):
        self.assertEqual(
            load("reporting").totals("item,quantity,price\na,0,8\nb,1,4\n"), {"a": 0.0, "b": 4.0}
        )


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
