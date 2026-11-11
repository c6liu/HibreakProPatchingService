import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "eink_migration_image", ROOT / "tools/add-eink-migration-to-gsi.py",
)
overlay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(overlay)


class EinkMigrationImageTests(unittest.TestCase):
    def test_file_context_is_exact_and_cannot_be_added_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contexts"
            path.write_text("/system/bin(/.*)? u:object_r:system_file:s0\n")
            overlay.prepare_file_contexts(path)
            self.assertIn(f"/system/bin/a9_eink_server {overlay.EXEC_CONTEXT}\n", path.read_text())
            with self.assertRaisesRegex(ValueError, "already exists"):
                overlay.prepare_file_contexts(path)

    def test_service_uses_transition_and_package_registry_groups(self):
        rc = (ROOT / "tools/display/hibreak-eink-migration.rc").read_text()
        self.assertIn("service a9_eink_server /system/bin/a9_eink_server\n", rc)
        self.assertIn("    group root system package_info\n", rc)
        self.assertNotIn("seclabel", rc)


if __name__ == "__main__":
    unittest.main()
