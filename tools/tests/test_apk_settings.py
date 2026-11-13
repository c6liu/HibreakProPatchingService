from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
APP = "{http://schemas.android.com/apk/res-auto}"
ANDROID = "{http://schemas.android.com/apk/res/android}"
SOURCE = ROOT / "a9_accessibility_service/res/xml/root_preferences.xml"


class SettingsResourceTests(unittest.TestCase):
    def test_hd_label_and_saved_mode_remain_compatible(self):
        arrays = ET.parse(ROOT / "a9_accessibility_service/res/values/arrays.xml").getroot()
        self.assertEqual(arrays.find("string-array[@name='refresh_options']")[0].text,
                         "@string/hd")
        self.assertEqual(arrays.find("string-array[@name='refresh_values']")[0].text, "2")
        strings = ET.parse(ROOT / "a9_accessibility_service/res/values/strings.xml").getroot()
        self.assertEqual(strings.find("string[@name='hd']").text, "HD")
        manager = (ROOT / "a9_accessibility_service/src/com/lmqr/ha9_comp_service/"
                   "RefreshModeManager.kt").read_text()
        self.assertIn("SMOOTH(Commands.SPEED_SMOOTH, 2)", manager)
        commands = (ROOT / "a9_accessibility_service/src/com/lmqr/ha9_comp_service/"
                    "command_runners/Commands.kt").read_text()
        self.assertIn('const val SPEED_SMOOTH = "s"', commands)

    def test_new_install_defaults_to_fast_and_display_controls_on(self):
        root = ET.parse(SOURCE).getroot()
        refresh = next(node for node in root.iter()
                       if node.get(APP + "key") == "refresh_setting")
        self.assertEqual(refresh.get(APP + "defaultValue"), "1")
        manager = (ROOT / "a9_accessibility_service/src/com/lmqr/ha9_comp_service/"
                   "RefreshModeManager.kt").read_text()
        self.assertIn('getString("refresh_setting", "1")', manager)
        controls = (ROOT / "a9_accessibility_service/src/com/lmqr/ha9_comp_service/"
                    "DisplaySettingsManager.kt").read_text()
        self.assertIn("index < 2 && sharedPreferences.getBoolean(keys[index], true)", controls)

    def test_settings_and_menu_use_standard_material3(self):
        themes = ET.parse(ROOT / "a9_accessibility_service/res/values/themes.xml").getroot()
        base = themes.find("style[@name='Theme.Ha9_comp_service']")
        self.assertEqual(base.get("parent"), "Theme.Material3.DayNight.NoActionBar")
        settings = themes.find("style[@name='Theme.Ha9_comp_service.Settings']")
        self.assertEqual(settings.get("parent"), "Theme.Ha9_comp_service")
        self.assertFalse(any((item.text or "").startswith("#") for item in base))

        night = ET.parse(ROOT / "a9_accessibility_service/res/values-night/themes.xml").getroot()
        self.assertEqual(len(night), 0)

        toolbar = ET.parse(
            ROOT / "a9_accessibility_service/res/layout/settings_activity.xml"
        ).getroot().find("com.google.android.material.appbar.MaterialToolbar")
        self.assertEqual(toolbar.get(ANDROID + "background"), "?attr/colorSurface")
        self.assertNotIn(ANDROID + "theme", toolbar.attrib)
        menu = ET.parse(ROOT / "a9_accessibility_service/res/layout/floating_menu_layout.xml").getroot()
        self.assertEqual(len(menu.findall(".//com.google.android.material.button.MaterialButton")), 5)
        self.assertEqual(len(menu.findall(".//com.google.android.material.materialswitch.MaterialSwitch")), 3)
        for source in ("SettingsActivity.kt", "A9AccessibilityService.kt"):
            text = (ROOT / "a9_accessibility_service/src/com/lmqr/ha9_comp_service" / source).read_text()
            self.assertIn("ThemeOverlay_Material3_DynamicColors_DayNight", text)

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
                             ["clear", "open_menu", "dummy", "dummy", "dummy", "dummy"])

    def test_supported_controls_and_dependencies(self):
        root = ET.parse(SOURCE).getroot()
        keyed = {node.get(APP + "key"): node for node in root.iter()
                 if node.get(APP + "key")}
        self.assertFalse(any(key.startswith("static_lockscreen") for key in keyed))
        self.assertNotIn("disable_show_per_app_aod_settings", keyed)
        self.assertIn("aod_invert", keyed)
        self.assertNotIn("override_max_brightness", keyed)
        self.assertEqual(keyed["frontlight_native_brightness"].get(APP + "defaultValue"), "true")
        self.assertIn("allow_custom_broadcast", keyed)
        self.assertEqual(keyed["per_app_refresh_modes"].tag,
                         "com.lmqr.ha9_comp_service.PerAppRefreshPagePreference")
        self.assertEqual(keyed["per_app_refresh_modes"].get(APP + "dependency"),
                         "disable_perapprefresh")
        self.assertNotIn(APP + "dependency", keyed["refresh_setting"].attrib)
        for node in root.iter("SwitchPreferenceCompat"):
            self.assertEqual(node.get(APP + "widgetLayout"), "@layout/preference_material_switch")

    def test_native_brightness_dump_permission_is_allowlisted(self):
        app = ROOT / "a9_accessibility_service"
        requested = {node.get(ANDROID + "name") for node in
                     ET.parse(app / "AndroidManifest.xml").getroot().findall("uses-permission")}
        allowed = {node.get("name") for node in
                   ET.parse(app / "privapp-permissions-accessibility.xml").getroot().iter("permission")}
        self.assertIn("android.permission.DUMP", requested)
        self.assertIn("android.permission.DUMP", allowed)

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

    def test_launch_app_actions_have_a_target_for_each_gesture(self):
        action_keys = (
            "top_single_press_eink_action",
            "top_double_press_eink_action",
            "top_long_press_eink_action",
            "top_single_press_eink_action_screen_off",
            "top_double_press_eink_action_screen_off",
            "top_long_press_eink_action_screen_off",
            "single_press_eink_action",
            "double_press_eink_action",
            "long_press_eink_action",
            "single_press_eink_action_screen_off",
            "double_press_eink_action_screen_off",
            "long_press_eink_action_screen_off",
        )
        settings = (ROOT / "a9_accessibility_service/src/com/lmqr/ha9_comp_service/"
                    "AppLaunchSettings.kt").read_text()
        manager = (ROOT / "a9_accessibility_service/src/com/lmqr/ha9_comp_service/"
                   "button_mapper/ButtonActionManager.kt").read_text()
        action = (ROOT / "a9_accessibility_service/src/com/lmqr/ha9_comp_service/"
                  "button_mapper/LaunchAppButtonAction.kt").read_text()
        shared = (ROOT / "a9_accessibility_service/src/com/lmqr/ha9_comp_service/"
                  "ButtonActionSettings.kt").read_text()
        picker = (ROOT / "a9_accessibility_service/src/com/lmqr/ha9_comp_service/"
                  "ActionTargetPickerActivity.kt").read_text()
        launch = (ROOT / "a9_accessibility_service/src/com/lmqr/ha9_comp_service/"
                  "button_mapper/LaunchTarget.kt").read_text()
        for key in action_keys:
            with self.subTest(action=key):
                self.assertIn(f'"{key}"', shared)
        for source in (settings, manager):
            self.assertIn("ButtonActionSettings.actionKeys", source)
        self.assertIn("queryIntentActivities", picker)
        self.assertIn("getLaunchIntentForPackage", action)
        self.assertIn("FLAG_ACTIVITY_NEW_TASK", action)
        self.assertIn("ActivityNotFoundException", launch)
        self.assertIn("LaunchShortcutButtonAction(preferenceKey)", manager)
        self.assertIn("ListPreference.SimpleSummaryProvider.getInstance()", settings)

    def test_screen_off_clear_is_not_offered(self):
        root = ET.parse(ROOT / "a9_accessibility_service/res/values/arrays.xml").getroot()
        entries = root.find("string-array[@name='button_action_entries_screen_off']")
        values = root.find("string-array[@name='button_action_values_screen_off']")
        self.assertEqual(len(entries), len(values))
        self.assertNotIn("clear", [item.text for item in values])

    def test_target_picker_is_internal_and_material3(self):
        manifest = ET.parse(ROOT / "a9_accessibility_service/AndroidManifest.xml").getroot()
        picker = manifest.find("application/activity[@android:name='.ActionTargetPickerActivity']",
                               {"android": ANDROID[1:-1]})
        self.assertEqual(picker.get(ANDROID + "exported"), "false")
        layout = ET.parse(ROOT / "a9_accessibility_service/res/layout/action_target_picker.xml").getroot()
        for tag in ("appbar.MaterialToolbar", "tabs.TabLayout", "textfield.TextInputLayout"):
            self.assertIsNotNone(layout.find("com.google.android.material." + tag))

    def test_video_refresh_toggle_defaults_off_and_is_explicit(self):
        layout = ET.parse(ROOT / "a9_accessibility_service/res/layout/floating_menu_layout.xml").getroot()
        toggle = next(node for node in layout.iter()
                      if node.get("{http://schemas.android.com/apk/res/android}id")
                      == "@+id/video_optimized_refresh")
        self.assertEqual(toggle.get("{http://schemas.android.com/apk/res/android}text"),
                         "Video refresh (experimental)")
        refresh_source = (ROOT / "a9_accessibility_service/src/com/lmqr/ha9_comp_service/"
                          "CameraLiveRefresh.kt").read_text()
        self.assertNotIn('.getBoolean("video_optimized_refresh"', refresh_source)

    def test_camera_live_refresh_preference_updates_the_active_overlay(self):
        root = ET.parse(SOURCE).getroot()
        cameras = [node for node in root.iter() if node.get(APP + "key") == "camera_live_refresh"]
        self.assertEqual(len(cameras), 1)
        self.assertEqual(cameras[0].get(APP + "defaultValue"), "true")
        service = (ROOT / "a9_accessibility_service/src/com/lmqr/ha9_comp_service/"
                   "A9AccessibilityService.kt").read_text()
        self.assertIn('"camera_live_refresh" -> cameraLiveRefresh?.update()', service)

    def test_app_picker_uses_standard_preference_layout(self):
        settings = (ROOT / "a9_accessibility_service/src/com/lmqr/ha9_comp_service/"
                    "AppLaunchSettings.kt").read_text()
        self.assertNotIn("layoutResource", settings)
