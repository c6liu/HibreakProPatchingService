import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
APP = "{http://schemas.android.com/apk/res-auto}"
SOURCE = ROOT / "a9_accessibility_service/res/xml/root_preferences.xml"


class SettingsResourceTests(unittest.TestCase):
    def test_category_order_and_button_mappings(self):
        root = ET.parse(SOURCE).getroot()
        categories = sorted(root, key=lambda node: int(node.get(APP + "order")))
        self.assertEqual([node.get(APP + "title") for node in categories], [
            "Top Action Button Settings", "Bottom Action Button Settings",
            "EInk Service Settings", "Refresh Mode Settings",
            "Per-App Refresh Modes", "Color Scheme",
        ])
        for category, prefix in zip(categories, ("top_", "")):
            self.assertEqual([node.get(APP + "key") for node in category], [
                prefix + key for key in (
                    "single_press_eink_action", "double_press_eink_action",
                    "long_press_eink_action", "single_press_eink_action_screen_off",
                    "double_press_eink_action_screen_off",
                    "long_press_eink_action_screen_off",
                )
            ])
            self.assertEqual([node.get(APP + "defaultValue") for node in category],
                             ["clear", "open_menu", "dummy", "clear", "dummy", "dummy"])

    def test_supported_controls_and_dependencies(self):
        root = ET.parse(SOURCE).getroot()
        keyed = {node.get(APP + "key"): node for node in root.iter()
                 if node.get(APP + "key")}
        self.assertFalse(any(key.startswith("static_lockscreen") for key in keyed))
        self.assertNotIn("disable_show_per_app_aod_settings", keyed)
        self.assertIn("aod_invert", keyed)
        self.assertEqual(keyed["override_max_brightness"].get(APP + "enabled"), "false")
        self.assertEqual(keyed["per_app_refresh_modes"].get(APP + "dependency"),
                         "disable_perapprefresh")
        self.assertNotIn(APP + "dependency", keyed["refresh_setting"].attrib)


class PatchedApkSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.apktool = Path(os.environ.get("APKTOOL_JAR", ROOT / "local/apktool.jar"))
        base = ROOT / "local/A9AccessibilityService.apk"
        if not shutil.which("java") or not cls.apktool.is_file() or not base.is_file():
            raise unittest.SkipTest("Tested base APK, apktool and Java are needed")
        (ROOT / "build").mkdir(exist_ok=True)
        tmp = tempfile.TemporaryDirectory(prefix="apk-settings-test-", dir=ROOT / "build")
        cls.addClassCleanup(tmp.cleanup)
        cls.work = Path(tmp.name)
        cls.decoded = cls.work / "app"
        cls.run_command("java", "-jar", cls.apktool, "d", base, "-o", cls.decoded)
        cls.run_command("python3", ROOT / "tools/patch-apk.py", cls.decoded)

    @staticmethod
    def run_command(*args):
        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def test_source_preferences_reach_offline_build(self):
        root = ET.parse(self.decoded / "res/xml/root_preferences.xml").getroot()
        source = ET.parse(SOURCE).getroot()
        actual = {node.get(APP + "key"): node.attrib for node in root.iter()
                  if node.get(APP + "key")}
        for node in source.iter():
            key = node.get(APP + "key")
            if key:
                self.assertEqual(actual[key], node.attrib)
        self.assertIn("camera_live_refresh", actual)
        service = (self.decoded /
                   "smali/com/lmqr/ha9_comp_service/A9AccessibilityService.smali").read_text()
        self.assertNotIn('const-string v9, "disable_show_per_app_aod_settings"', service)
        self.assertIn("getStaticAodLinearLayout()", service)

    def test_dynamic_preferences_are_wired_and_assemble(self):
        smali = self.decoded / "smali/com/lmqr/ha9_comp_service"
        fragment = (smali / "SettingsActivity$SettingsFragment.smali").read_text()
        self.assertIn("PerAppRefreshSettings;->populate", fragment)
        preference = (smali / "PerAppRefreshPreference.smali").read_text()
        self.assertIn("->persistInt(I)Z", preference)
        self.assertIn("->getPersistedInt(I)I", preference)
        self.assertIn("->remove(Ljava/lang/String;)", preference)
        helper = (smali / "PerAppRefreshSettings.smali").read_text()
        self.assertIn('const-string v9, "package:"', helper)
        self.assertIn("->queryIntentActivities", helper)
        self.run_command("java", "-jar", self.apktool, "b", self.decoded,
                         "-o", self.work / "settings.apk")
        self.assertTrue((self.work / "settings.apk").is_file())
