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
        self.assertIn("(allow priv_app hibreak_eink (unix_stream_socket (connectto read write)))", cil)

    def test_candidate_has_framework_helper_scaffold_without_broad_service_type_grants(self):
        cil = (ROOT / "tools/display/hibreak-eink-candidate.cil").read_text()
        for service in ("activity_service", "input_service", "settings_service"):
            self.assertIn(f"(allow hibreak_eink {service} (service_manager (find)))", cil)
        self.assertIn("(allow hibreak_eink system_file (file (read open getattr map execute execute_no_trans)))", cil)
        self.assertIn("(allow hibreak_eink toolbox_exec (file (read open getattr map execute execute_no_trans)))", cil)
        self.assertIn("(allow system_server hibreak_eink (binder (call)))", cil)
        self.assertNotIn("(allow hibreak_eink service_manager_type", cil)

    def test_init_bridge_client_grants_only_property_set(self):
        cil = (ROOT / "tools/display/hibreak-eink-bridge-client.cil").read_text()
        rules = [line for line in cil.splitlines() if line.startswith("(")]
        self.assertEqual(rules, [
            "(allow hibreak_eink hibreak_eink_bridge_prop (property_service (set)))",
        ])

    def test_init_bridge_contexts_must_match_tested_exact_enum(self):
        source = (ROOT / "tools/display/hibreak-init-eink-bridge-property-contexts").read_text()
        migration.validate_bridge_contexts([*self.entries, *parse_contexts("bridge", source)])
        cases = (
            "",
            source.replace("exact enum 0 1", "prefix enum 0 1", 1),
            source.replace("exact enum 0 1", "exact string", 1),
            source.replace("hibreak_eink_bridge_prop", "system_prop", 1),
            source + source,
        )
        for text in cases:
            with self.subTest(text=text), self.assertRaises(ValueError):
                migration.validate_bridge_contexts([*self.entries, *parse_contexts("bridge", text)])

    def test_frontlight_preserves_missing_baseline_permissions(self):
        baseline = {("init", "file", "read"), ("init", "file", "write"),
                    ("system_server", "file", "open")}
        current = {("init", "file", "read"), ("hibreak_eink", "file", "open")}
        self.assertEqual(migration.frontlight_preservation_rules(baseline, current), [
            "(allow init hibreak_eink_frontlight (file (write)))",
            "(allow system_server hibreak_eink_frontlight (file (open)))",
        ])
        with self.assertRaises(ValueError):
            migration.frontlight_preservation_rules({("init", "dir", "search")}, set())

    def test_final_frontlight_xperms_preserve_existing_and_display_inheritance(self):
        baseline = {("init", "ioctl", 1)}
        display = {("hibreak_display", "ioctl", 2)}
        actual = baseline | display
        migration.validate_frontlight_xperms(actual, baseline, display_migrated=True,
                                            generic_display=display)
        with self.assertRaisesRegex(ValueError, "Display helper extended frontlight"):
            migration.validate_frontlight_xperms(actual, baseline, display_migrated=True,
                                                generic_display=set())
        with self.assertRaisesRegex(ValueError, "Existing extended sysfs"):
            migration.validate_frontlight_xperms(actual | {("other", "ioctl", 3)}, baseline,
                                                display_migrated=True, generic_display=display)

    def test_complete_candidate_is_scoped_to_two_frontlight_paths(self):
        cil = (ROOT / "tools/display/hibreak-eink-runtime.cil").read_text()
        self.assertEqual(cil.count("(genfscon sysfs "), 2)
        for path in migration.FRONTLIGHT_PATHS:
            self.assertIn(f'(genfscon sysfs "{path}"', cil)
        self.assertIn("(allow hibreak_eink packages_list_file (file (open read getattr)))", cil)
        self.assertNotIn("(allow hibreak_eink sysfs ", cil)

    def test_extended_file_permissions_expand_sources(self):
        class NotConditional(Exception):
            pass

        class Source:
            def expand(self):
                return ("init", "system_server")

        class Rule:
            source = Source()
            xperm_type = "ioctl"
            perms = (0x5401, 0x5450)

            @property
            def conditional(self):
                raise NotConditional()

        class Query:
            def __init__(self, policy, **kwargs):
                self.kwargs = kwargs

            def results(self):
                return [Rule()]

        permissions = migration.extended_file_permissions(None, "sysfs", Query, NotConditional)
        self.assertEqual(permissions, {
            (source, "ioctl", permission)
            for source in ("init", "system_server") for permission in (0x5401, 0x5450)
        })
