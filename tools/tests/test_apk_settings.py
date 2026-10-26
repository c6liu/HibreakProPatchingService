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
        self.assertNotIn("override_max_brightness", keyed)
        self.assertIn("allow_custom_broadcast", keyed)
        self.assertEqual(keyed["per_app_refresh_modes"].tag,
                         "com.lmqr.ha9_comp_service.PerAppRefreshPagePreference")
        self.assertEqual(keyed["per_app_refresh_modes"].get(APP + "dependency"),
                         "disable_perapprefresh")
        self.assertNotIn(APP + "dependency", keyed["refresh_setting"].attrib)

    def test_per_app_page_has_reset_and_no_expansion(self):
        root = ET.parse(SOURCE.with_name("per_app_preferences.xml")).getroot()
        self.assertEqual([node.get(APP + "key") for node in root],
                         ["reset_app_refresh_modes", "per_app_apps"])
        self.assertFalse(any(APP + "initialExpandedChildrenCount" in node.attrib
                             for node in root.iter()))

    def test_directional_actions_replace_unsupported_lcd_controls(self):
        root = ET.parse(ROOT / "a9_accessibility_service/res/values/arrays.xml").getroot()
        entries = root.find("string-array[@name='button_action_entries']")
        values = root.find("string-array[@name='button_action_values']")
        self.assertEqual(
            [(entry.text, value.text) for entry, value in zip(entries, values)][:5],
            [("Clear Screen", "clear"), ("Up", "dpad_up"), ("Down", "dpad_down"),
             ("Left", "dpad_left"), ("Right", "dpad_right")],
        )
        self.assertNotIn("Toggle Night Light", [item.text for item in entries])
        self.assertNotIn("Toggle Backlight", [item.text for item in entries])
        self.assertNotIn("toggle_night_light", [item.text for item in values])
        self.assertNotIn("toggle_backlight", [item.text for item in values])


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
        self.assertIn('const-string v4, "per_app_page"', helper)
        self.assertIn("->setPreferencesFromResource", helper)
        self.assertNotIn("@PER_APP_XML@", helper)
        page = (smali / "PerAppRefreshPagePreference.smali").read_text()
        self.assertIn("->startActivity", page)
        reset = (smali / "ResetAppRefreshPreference.smali").read_text()
        self.assertIn("->setNegativeButton", reset)
        self.assertIn("->setPositiveButton", reset)
        self.assertIn('const-string v3, "package:None"', reset)
        self.assertIn("->remove(Ljava/lang/String;)", reset)
        self.assertNotIn("->clear()", reset)
        receiver = (smali / "A9AccessibilityService$receiverEink$1.smali").read_text()
        self.assertIn('"allow_custom_broadcast"', receiver)
        self.assertIn('"EINK_REFRESH_SPEED_HYPER"', receiver)
        self.assertIn("->changeMode", receiver)
        self.assertEqual(ET.parse(self.decoded / "res/xml/per_app_preferences.xml")
                         .getroot()[0].get(APP + "key"), "reset_app_refresh_modes")
        arrays = ET.parse(self.decoded / "res/values/arrays.xml").getroot()
        entries = arrays.find("string-array[@name='button_action_entries']")
        values = arrays.find("string-array[@name='button_action_values']")
        self.assertEqual(
            [(entry.text, value.text) for entry, value in zip(entries, values)][:5],
            [("Clear Screen", "clear"), ("Up", "dpad_up"), ("Down", "dpad_down"),
             ("Left", "dpad_left"), ("Right", "dpad_right")],
        )
        action_manager = (smali / "button_mapper/ButtonActionManager.smali").read_text()
        for direction in ("up", "down", "left", "right"):
            self.assertIn(f'"dpad_{direction}"', action_manager)
        self.assertNotIn("ToggleNightLightAction", action_manager)
        self.assertNotIn("ToggleBacklightAction", action_manager)
        self.assertFalse((self.decoded / "smali/SystemSettingsManager.smali").exists())
        self.assertFalse((smali / "button_mapper/ToggleNightLightAction.smali").exists())
        self.assertFalse((smali / "button_mapper/ToggleBacklightAction.smali").exists())
        dpad = (smali / "button_mapper/DpadButtonAction.smali").read_text()
        self.assertIn("->runCommands", dpad)
        daemon = (ROOT / "a9_eink_daemon/eink_daemon.c").read_text()
        for command, code in (("up", "19"), ("down", "20"),
                              ("left", "21"), ("right", "22")):
            self.assertIn(f'command, "dpad_{command}"', daemon)
            self.assertIn(f'sendDpadKey("{code}")', daemon)
        self.run_command("java", "-jar", self.apktool, "b", self.decoded,
                         "-o", self.work / "settings.apk")
        self.assertTrue((self.work / "settings.apk").is_file())
