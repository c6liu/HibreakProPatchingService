import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("xrz_compat", ROOT / "tools/image/add-xrz-compat-to-gsi.py")
overlay = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = overlay
SPEC.loader.exec_module(overlay)


class XrzContextTests(unittest.TestCase):
    PLAT = ("# fixture\nvendor. u:object_r:vendor_default_prop:s0\n"
            "ro.vendor. u:object_r:vendor_default_prop:s0\n")

    def test_only_four_exact_properties_are_relabelled(self):
        other = [("vendor", "vendor.radio. u:object_r:vendor_radio_prop:s0\n")]
        updated = overlay.add_property_contexts(self.PLAT, other)
        entries = overlay.parse_contexts("platform", updated)
        entries.extend(overlay.parse_contexts(*other[0]))
        for name in overlay.PROPERTIES:
            result = overlay.resolve_context(name, entries)
            self.assertEqual((result.label, result.match, result.value_type),
                             (overlay.XRZ_LABEL, "exact", ("string",)))
        self.assertEqual(len(overlay.PROPERTIES), 4)
        self.assertIn("ro.vendor.xrz.screen_type", overlay.PROPERTIES)
        for name in ("vendor.xrz.global_refresh_mode", "vendor.xrz.hwc_idle_extra",
                     "ro.vendor.xrz.screen_type_extra", "ro.vendor.xrz.pen_type"):
            self.assertEqual(overlay.resolve_context(name, entries).label, overlay.DEFAULT_LABEL)
        self.assertEqual(overlay.resolve_context("vendor.radio.example", entries).label,
                         "u:object_r:vendor_radio_prop:s0")
        self.assertNotIn("vendor.xrz. u:object_r:vendor_xrz_prop:s0", updated)
        self.assertIn("# hibreak-xrz-graphics-compat-v2", updated)

    def test_longest_prefix_and_exact_matching(self):
        entries = overlay.parse_contexts("fixture", """
vendor. u:object_r:default_prop:s0
vendor.test u:object_r:prefix_prop:s0 prefix string
vendor.test u:object_r:exact_prop:s0 exact string
""")
        self.assertEqual(overlay.resolve_context("vendor.test", entries).label,
                         "u:object_r:exact_prop:s0")
        self.assertEqual(overlay.resolve_context("vendor.testing", entries).label,
                         "u:object_r:prefix_prop:s0")
        self.assertEqual(overlay.resolve_context("vendor.other", entries).label,
                         "u:object_r:default_prop:s0")

    def test_existing_specific_or_ambiguous_contexts_are_rejected(self):
        cases = (
            ("vendor", "vendor.xrz. u:object_r:other_prop:s0\n", "Expected generic"),
            ("vendor", f"{overlay.PROPERTIES[0]} {overlay.DEFAULT_LABEL} exact string\n",
             "already has an exact"),
            ("vendor", "vendor. u:object_r:other_prop:s0\n", "Ambiguous"),
            ("vendor", "vendor.xrz. u:object_r:vendor_default_prop:s0 prefix int\n",
             "Expected generic"),
        )
        for source, text, message in cases:
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, message):
                overlay.add_property_contexts(self.PLAT, [(source, text)])

    def test_invalid_or_missing_contexts_are_rejected(self):
        for text in ("vendor.\n", "vendor. u:object_r:vendor_default_prop:s0 invalid\n"):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "Invalid property"):
                overlay.parse_contexts("fixture", text)
        with self.assertRaisesRegex(ValueError, "No property context matches"):
            overlay.add_property_contexts("# no vendor context\n", [])
        with self.assertRaisesRegex(ValueError, "already has an exact"):
            overlay.add_property_contexts(overlay.add_property_contexts(self.PLAT, []), [])


class XrzPolicyTests(unittest.TestCase):
    def test_compiled_policy_rejects_lost_or_extra_permissions(self):
        baseline = {("system_server", "file", "read")}
        permissions = baseline | {overlay.COMPOSER_SET}
        policy = SimpleNamespace(lookup_type=lambda _name: SimpleNamespace(
            attributes=lambda: ("property_type", "vendor_xrz_prop_31_0")))
        modules = {"setools": SimpleNamespace(TERuleQuery=object()),
                   "setools.exception": SimpleNamespace(RuleNotConditional=Exception)}
        with mock.patch.dict(sys.modules, modules), \
                mock.patch.object(overlay, "effective_permissions", return_value=permissions):
            overlay.validate_xrz_policy(policy, baseline)
            permissions.remove(("system_server", "file", "read"))
            with self.assertRaisesRegex(ValueError, "Property permissions differ"):
                overlay.validate_xrz_policy(policy, baseline)
            permissions.add(("system_server", "file", "read"))
            permissions.add(("untrusted_app", "property_service", "set"))
            with self.assertRaisesRegex(ValueError, "Property permissions differ"):
                overlay.validate_xrz_policy(policy, baseline)

    def test_preserves_missing_access_and_adds_only_composer_set(self):
        baseline = {
            ("composer", "file", "read"),
            ("system_server", "file", "read"),
            ("system_server", "file", "open"),
            ("vendor_init", "property_service", "set"),
        }
        mapped = {("composer", "file", "read"), overlay.COMPOSER_SET}
        self.assertEqual(overlay.preservation_rules(baseline, mapped), [
            "(allow system_server vendor_xrz_prop (file (open read)))",
            "(allow vendor_init vendor_xrz_prop (property_service (set)))",
        ])

    def test_unexpected_or_invalid_permissions_are_rejected(self):
        cases = (
            ({overlay.COMPOSER_SET}, {overlay.COMPOSER_SET}, "already has"),
            (set(), set(), "does not grant"),
            (set(), {overlay.COMPOSER_SET, ("unexpected", "file", "read")}, "unexpected permissions"),
            ({("bad)name", "file", "read")}, {overlay.COMPOSER_SET}, "Unsupported SELinux identifier"),
        )
        for baseline, mapped, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                overlay.preservation_rules(baseline, mapped)

    def test_conditional_rules_cannot_be_silently_widened(self):
        class NotConditional(Exception):
            pass

        class Source:
            def expand(self):
                return ("a", "b")

        class Rule:
            source = Source()
            tclass = "file"
            perms = {"read", "open"}

            @property
            def conditional(self):
                raise NotConditional()

        class ConditionalRule(Rule):
            @property
            def conditional(self):
                return True

        class PropertyServiceRule(Rule):
            tclass = "property_service"
            perms = {"set"}

        class Query:
            rules = [Rule(), PropertyServiceRule()]

            def __init__(self, _policy, **kwargs):
                if "tclass" in kwargs:
                    raise AssertionError("The permission comparison must cover every object class")

            def results(self):
                return self.rules

        result = overlay.effective_permissions(None, "vendor_default_prop", Query, NotConditional)
        self.assertEqual(result, {
            ("a", "file", "read"), ("a", "file", "open"),
            ("b", "file", "read"), ("b", "file", "open"),
            ("a", "property_service", "set"), ("b", "property_service", "set"),
        })
        Query.rules = [ConditionalRule()]
        with self.assertRaisesRegex(ValueError, "Conditional property permission"):
            overlay.effective_permissions(None, "vendor_default_prop", Query, NotConditional)


class XrzImageTests(unittest.TestCase):
    def test_ext4_roundtrip_check_only_and_no_overwrite(self):
        for tool in ("debugfs", "mke2fs", "e2fsck", "resize2fs", "dumpe2fs"):
            if not shutil.which(tool):
                self.skipTest(f"Missing {tool}")
        with tempfile.TemporaryDirectory(prefix="xrz-overlay-test-") as directory:
            work = Path(directory)
            source, output = work / "source.img", work / "output.img"
            with source.open("wb") as stream:
                stream.truncate(32 * 1024 * 1024)
            subprocess.run(["mke2fs", "-q", "-t", "ext4", "-F", source], check=True)
            for path in ("system", "system/etc", "system/etc/selinux",
                         "system/etc/selinux/mapping", "system/etc/init"):
                overlay.image.run("debugfs", "-w", "-R", f"mkdir {path}", str(source))
            original = work / "original"
            original.write_text("original content\n")
            destinations = (
                "system/etc/selinux/plat_sepolicy.cil",
                overlay.MAPPING,
                overlay.PLAT_CONTEXTS,
                "system/etc/selinux/plat_sepolicy_and_mapping.sha256",
                "system/etc/init/hibreak-ir-hal.rc",
            )
            for destination in destinations:
                overlay.image.install(source, original, destination, "0100644",
                                      "u:object_r:system_file:s0", work)
            original_source = source.read_bytes()
            contents = ("IR and XRZ platform policy\n", "XRZ mapping\n",
                        "exact XRZ contexts\n", "new digest\n")
            files = []
            for index, content in enumerate(contents):
                path = work / f"new-{index}"
                path.write_text(content)
                files.append(path)
            argv = ["xrz-overlay", str(source), str(output), "--vendor-image", str(source),
                    "--secilc", "true"]
            with mock.patch.object(overlay, "prepare_compatibility", return_value=files), \
                    mock.patch.object(sys, "argv", [*argv, "--check-only"]):
                overlay.main()
            self.assertFalse(output.exists())
            with mock.patch.object(overlay, "prepare_compatibility", return_value=files), \
                    mock.patch.object(sys, "argv", argv):
                overlay.main()
                with self.assertRaises(SystemExit):
                    overlay.main()
            self.assertEqual(source.read_bytes(), original_source)
            for destination, content in zip(destinations[:4], contents):
                actual = overlay.image.run(
                    "debugfs", "-R", f"cat {destination}", str(output),
                ).stdout.decode()
                self.assertEqual(actual, content)
                stat = overlay.image.run(
                    "debugfs", "-R", f"stat {destination}", str(output),
                ).stdout.decode()
                self.assertIn("Mode:  0644", stat)
                self.assertIn("u:object_r:system_file:s0", stat)
            self.assertEqual(
                overlay.image.run("debugfs", "-R", f"cat {destinations[4]}", str(output)).stdout,
                b"original content\n",
            )

    def test_failed_build_removes_only_the_new_output(self):
        with tempfile.TemporaryDirectory(prefix="xrz-failed-build-") as directory:
            work = Path(directory)
            source, output = work / "source.img", work / "output.img"
            source.write_bytes(b"source")
            inputs = [work / f"input-{index}" for index in range(4)]
            with mock.patch.object(overlay.image, "run", side_effect=OSError("copy failed")):
                with self.assertRaisesRegex(OSError, "copy failed"):
                    overlay.build_image(source, output, inputs, work)
            self.assertFalse(output.exists())
            self.assertEqual(source.read_bytes(), b"source")


if __name__ == "__main__":
    unittest.main()
