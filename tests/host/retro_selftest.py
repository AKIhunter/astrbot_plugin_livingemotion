"""Small tests of P8 evidence integrity, with no product or AstrBot imports."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from retro_common import Evidence, digest, product_files, scrubbed_env


class HarnessIntegrity(unittest.TestCase):
    def test_source_hash_covers_runtime_and_assets_not_legacy_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for rel, text in {
                "main.py": "pass", "metadata.yaml": "version: 0.2.0",
                "runtime/application.py": "pass", "pages/livingemotion/app.mjs": "export {};",
                "tests/host/evidence-v4.29.4.json": '{"success":true}',
                "docs/verification-host.md": "old",
            }.items():
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            initial = product_files(root)
            self.assertEqual(set(initial), {
                "main.py", "metadata.yaml", "runtime/application.py", "pages/livingemotion/app.mjs",
            })
            (root / "runtime/application.py").write_text("changed")
            self.assertNotEqual(digest(initial), digest(product_files(root)))
            changed = product_files(root)
            (root / "tests/host/evidence-v4.29.4.json").write_text('{"success":false}')
            self.assertEqual(changed, product_files(root))

    def test_source_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.py").symlink_to("/etc/hosts")
            with self.assertRaises(ValueError):
                product_files(root)

    def test_scrubbed_environment_is_allowlist(self):
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "synthetic", "GH_TOKEN": "synthetic",
            "HTTPS_PROXY": "http://127.0.0.1:1",
        }):
            env = scrubbed_env(Path("/synthetic-root"), Path("/synthetic-venv/bin/python"))
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("GH_TOKEN", env)
        self.assertNotIn("HTTPS_PROXY", env)
        self.assertEqual(env["ASTRBOT_ROOT"], "/synthetic-root")

    def test_preparation_is_never_final_acceptance(self):
        report = {"phase": "prepare", "checks": []}
        evidence = Evidence(report)
        evidence.check("host.ready", True)
        evidence.finish()
        self.assertTrue(report["success"])
        self.assertFalse(report["final_frozen_acceptance"])

    def test_any_failed_case_prevents_final_acceptance(self):
        report = {"phase": "final", "checks": []}
        evidence = Evidence(report)
        evidence.check("host.ready", True)
        evidence.check("product.unresolved", False)
        evidence.finish()
        self.assertFalse(report["success"])
        self.assertFalse(report["final_frozen_acceptance"])

    def test_hash_serialization_is_canonical(self):
        self.assertEqual(digest({"b": "2", "a": "1"}), digest({"a": "1", "b": "2"}))
        self.assertNotEqual(digest({"a": "1"}), digest({"a": "2"}))


if __name__ == "__main__":
    unittest.main()
