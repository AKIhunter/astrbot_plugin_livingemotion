"""Pure calculations and the injected full-reading coordinator stay isolated."""

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
                    allowed = ("json", "asyncio") if path.name == "catchup.py" else ("json",)
                    self.assertTrue(all(item.name in allowed for item in node.names))
                elif isinstance(node, ast.ImportFrom):
                    allowed = ("__future__", "dataclasses", "typing", "contracts")
                    if path.name == "catchup.py":
                        allowed += ("weakref",)
                    self.assertIn(node.module, allowed)
                    if node.module == "contracts":
                        self.assertEqual(node.level, 2)
                elif isinstance(node, ast.AsyncFunctionDef):
                    self.assertEqual(path.name, "catchup.py")
                    self.assertEqual(node.name, "prepare")

    def test_catchup_never_writes_energy_or_sends(self):
        tree = ast.parse((ROOT / "services/catchup.py").read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword):
                self.assertNotEqual(node.arg, "energy")
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", getattr(node.func, "attr", ""))
                self.assertNotIn(name, ("send_message", "open", "create_task", "sleep",
                                        "write_states", "reply_submitted", "execute"))
                if name == "send":
                    # Only the injected, guarded executor owns transport I/O.
                    self.assertIsInstance(node.func, ast.Attribute)
                    self.assertIsInstance(node.func.value, ast.Name)
                    self.assertEqual(node.func.value.id, "self")
        # All calculation helpers remain synchronous and independent of I/O.
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                self.assertFalse(any(isinstance(child, ast.Await) for child in ast.walk(node)))


if __name__ == "__main__":
    unittest.main()
