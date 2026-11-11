import importlib.util
from pathlib import Path
import re
import unittest

from tools.hibreak.properties import parse_contexts


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("eink_migration", ROOT / "tools/check-eink-migration.py")
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)


class EinkMigrationTests(unittest.TestCase):
    def setUp(self):
        self.additions = (ROOT / "tools/display/hibreak-eink-control-property-contexts").read_text()
        self.entries = parse_contexts("fixture", """
sys. u:object_r:system_prop:s0
persist.sys. u:object_r:system_prop:s0
vendor. u:object_r:vendor_default_prop:s0
""")

    def test_only_five_exact_typed_request_contexts_are_added(self):
        requests = migration.control_contexts(self.entries, self.additions)
        self.assertEqual(len(requests), 5)
        self.assertTrue(all(entry.match == "exact" for entry in requests))

    def test_existing_exact_request_or_invalid_context_is_rejected(self):
        exact = parse_contexts("conflict", "sys.hibreak.request.refresh_mode u:object_r:system_prop:s0 exact string")
        with self.assertRaisesRegex(ValueError, "already has an exact"):
            migration.control_contexts([*self.entries, *exact], self.additions)
        cases = (
            self.additions.replace("exact int", "prefix int", 1),
            self.additions.replace("exact int", "exact string", 1),
            self.additions.replace(migration.CONTROL_LABEL, "u:object_r:system_prop:s0", 1),
            self.additions + self.additions,
        )
        for additions in cases:
            with self.subTest(additions=additions), self.assertRaises(ValueError):
                migration.control_contexts(self.entries, additions)

    def test_bridge_only_writes_existing_destinations_with_validated_values(self):
        rc = (ROOT / "tools/display/hibreak-eink-control.rc").read_text()
        actions = re.findall(r"^on property:(\S+)=(\S+)\n    setprop (\S+) (\S+)$", rc, re.M)
        self.assertEqual(len(actions), 10)
        self.assertEqual({request for request, _, _, _ in actions}, set(migration.DESTINATIONS))
        for request, trigger, destination, value in actions:
            self.assertEqual(destination, migration.DESTINATIONS[request])
            types = migration.VALUE_TYPES[request]
            if types[0] == "enum":
                self.assertIn(trigger, types[1:])
                self.assertEqual(value, trigger)
            else:
                self.assertEqual(trigger, "*")
                self.assertEqual(value, "${" + request + "}")
        for request in ("sys.hibreak.request.refresh_mode", "sys.hibreak.request.aod_invert"):
            self.assertEqual({trigger for name, trigger, _, _ in actions if name == request},
                             set(migration.VALUE_TYPES[request][1:]))
        self.assertNotIn("seclabel u:r:phhsu_daemon:s0", rc)

    def test_candidate_has_no_permissive_or_default_property_write_rules(self):
        cil = (ROOT / "tools/display/hibreak-eink-candidate.cil").read_text()
        self.assertNotIn("(typepermissive", cil)
        self.assertNotIn("(allow hibreak_eink system_prop", cil)
        self.assertNotIn("(allow hibreak_eink vendor_default_prop", cil)
        self.assertIn("(typeattributeset mlstrustedsubject (hibreak_eink))", cil)
        self.assertIn("(allow priv_app hibreak_eink (unix_stream_socket (connectto)))", cil)

    def test_candidate_has_framework_helper_scaffold_without_broad_service_type_grants(self):
        cil = (ROOT / "tools/display/hibreak-eink-candidate.cil").read_text()
        for service in ("activity_service", "input_service", "settings_service"):
            self.assertIn(f"(allow hibreak_eink {service} (service_manager (find)))", cil)
        self.assertIn("(allow hibreak_eink system_file (file (read open getattr map execute execute_no_trans)))", cil)
        self.assertIn("(allow hibreak_eink toolbox_exec (file (read open getattr map execute execute_no_trans)))", cil)
        self.assertNotIn("(allow hibreak_eink service_manager_type", cil)
