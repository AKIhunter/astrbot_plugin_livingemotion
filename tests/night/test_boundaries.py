"""Static ownership checks for the two pure T5 modules."""

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class OwnershipTests(unittest.TestCase):
    def test_imports_have_no_host_storage_memory_or_sender_dependencies(self):
        for path in (ROOT / "domain/night.py", ROOT / "services/catchup.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertTrue(all(item.name == "json" for item in node.names))
                elif isinstance(node, ast.ImportFrom):
                    self.assertIn(node.module, ("__future__", "dataclasses", "typing", "contracts"))
                    if node.module == "contracts":
                        self.assertEqual(node.level, 2)
                elif isinstance(node, ast.AsyncFunctionDef):
                    self.fail(f"unexpected async/I/O entry: {node.name}")

    def test_catchup_never_writes_energy_or_sends(self):
        tree = ast.parse((ROOT / "services/catchup.py").read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword):
                self.assertNotEqual(node.arg, "energy")
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", getattr(node.func, "attr", ""))
                self.assertNotIn(name, ("send", "send_message", "open", "create_task", "sleep"))


if __name__ == "__main__":
    unittest.main()
