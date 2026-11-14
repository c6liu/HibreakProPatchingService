from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
from tools.hibreak import eink_migration as overlay


class EinkMigrationImageTests(unittest.TestCase):
    def test_file_context_is_exact_and_cannot_be_added_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contexts"
            path.write_text("/system/bin(/.*)? u:object_r:system_file:s0\n")
            overlay.prepare_file_contexts(path)
            self.assertIn(f"/system/bin/eink_server {overlay.EXEC_CONTEXT}\n", path.read_text())
            with self.assertRaisesRegex(ValueError, "already exists"):
                overlay.prepare_file_contexts(path)

    def test_service_uses_transition_and_package_registry_groups(self):
        rc = (ROOT / "tools/display/hibreak-eink-migration.rc").read_text()
        self.assertIn("service eink_server /system/bin/eink_server\n", rc)
        self.assertIn("    group root system package_info\n", rc)
        self.assertNotIn("seclabel", rc)


if __name__ == "__main__":
    unittest.main()
