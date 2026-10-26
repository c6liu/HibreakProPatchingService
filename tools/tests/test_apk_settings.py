import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import uuid
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
APP = "{http://schemas.android.com/apk/res-auto}"
ANDROID = "{http://schemas.android.com/apk/res/android}"
SOURCE = ROOT / "a9_accessibility_service/res/xml/root_preferences.xml"


class SettingsResourceTests(unittest.TestCase):
    def test_settings_theme_uses_monochrome_material3(self):
        themes = ET.parse(ROOT / "a9_accessibility_service/res/values/themes.xml").getroot()
        settings = themes.find("style[@name='Theme.Ha9_comp_service.Settings']")
        self.assertEqual(settings.get("parent"), "Theme.Material3.DayNight.NoActionBar")
        items = {item.get("name"): item.text for item in settings.findall("item")}
        self.assertEqual(items["colorSurface"], "#FFFFFFFF")
        self.assertEqual(items["colorOnSurface"], "#FF000000")
        self.assertEqual(items["colorControlActivated"], "#FF000000")

        night = ET.parse(ROOT / "a9_accessibility_service/res/values-night/themes.xml").getroot()
        night_settings = night.find("style[@name='Theme.Ha9_comp_service.Settings']")
        night_items = {item.get("name"): item.text for item in night_settings.findall("item")}
        self.assertEqual(night_items["colorSurface"], "#FF000000")
        self.assertEqual(night_items["colorOnSurface"], "#FFFFFFFF")

        toolbar = ET.parse(
            ROOT / "a9_accessibility_service/res/layout/settings_activity.xml"
        ).getroot().find("androidx.appcompat.widget.Toolbar")
        self.assertEqual(toolbar.get(ANDROID + "background"), "?attr/colorSurface")
        self.assertEqual(toolbar.get(ANDROID + "theme"), "@style/ThemeOverlay.Material3.Light")

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
        for key in action_keys:
            with self.subTest(action=key):
                self.assertIn(f'"{key}"', settings)
                self.assertIn(f'"{key}"', manager)
        self.assertIn("queryIntentActivities", settings)
        self.assertIn("getLaunchIntentForPackage", action)
        self.assertIn("FLAG_ACTIVITY_NEW_TASK", action)
        self.assertIn("ActivityNotFoundException", action)
        self.assertIn("actionPreference.parent", settings)
        self.assertIn("actionPreference.order + 1", settings)
        self.assertIn("appPreference.isVisible = newValue == launchActionValue", settings)
        self.assertIn("ListPreference.SimpleSummaryProvider.getInstance()", settings)

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

    def test_app_picker_uses_standard_preference_layout(self):
        settings = (ROOT / "a9_accessibility_service/src/com/lmqr/ha9_comp_service/"
                    "AppLaunchSettings.kt").read_text()
        self.assertNotIn("layoutResource", settings)


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
        probe = cls.decoded / "smali/hibreak/tests/DpadActionProbe.smali"
        probe.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "tools/tests/smali/DpadActionProbe.smali", probe)
        public = ET.parse(cls.decoded / "res/values/public.xml").getroot()
        popup_probe = (ROOT / "tools/tests/smali/PopupProbe.smali").read_text()
        for token, kind, name in (
                ("@THEME@", "style", "Theme.Ha9_comp_service"),
                ("@LAYOUT@", "layout", "floating_menu_layout")):
            resource_id = public.find(f"public[@type='{kind}'][@name='{name}']").get("id")
            popup_probe = popup_probe.replace(token, resource_id)
        probe.with_name("PopupProbe.smali").write_text(popup_probe)
        shutil.copyfile(ROOT / "tools/tests/smali/RuntimeInstrumentation.smali",
                        probe.with_name("RuntimeInstrumentation.smali"))
        shutil.copyfile(ROOT / "tools/tests/smali/PerAppControlsProbe.smali",
                        probe.with_name("PerAppControlsProbe.smali"))
        shutil.copyfile(ROOT / "tools/tests/smali/SettingsActivityProbe.smali",
                        probe.with_name("SettingsActivityProbe.smali"))
        shutil.copyfile(ROOT / "tools/tests/smali/ScreenOffLaunchProbe.smali",
                        probe.with_name("ScreenOffLaunchProbe.smali"))
        if os.environ.get("HIBREAK_ADB_TESTS") == "1":
            android = "{http://schemas.android.com/apk/res/android}"
            cls.test_package = f"hibreak.tests.regression.p{uuid.uuid4().hex}"
            manifest = ET.Element("manifest", {"package": cls.test_package})
            for permission in ("WAKE_LOCK", "TURN_SCREEN_ON", "SYSTEM_ALERT_WINDOW"):
                ET.SubElement(manifest, "uses-permission", {
                    android + "name": "android.permission." + permission,
                })
            queries = ET.parse(cls.decoded / "AndroidManifest.xml").getroot().find("queries")
            if queries is not None:
                manifest.append(queries)
            application = ET.SubElement(manifest, "application", {
                android + "theme": "@style/Theme.Ha9_comp_service.Settings",
                android + "testOnly": "true",
            })
            activity = ET.SubElement(application, "activity", {
                android + "name": "hibreak.tests.SettingsActivityProbe",
                android + "exported": "true",
            })
            launcher = ET.SubElement(activity, "intent-filter")
            ET.SubElement(launcher, "action", {android + "name": "android.intent.action.MAIN"})
            ET.SubElement(launcher, "category", {android + "name": "android.intent.category.LAUNCHER"})
            ET.SubElement(manifest, "instrumentation", {
                android + "name": "hibreak.tests.RuntimeInstrumentation",
                android + "targetPackage": cls.test_package,
            })
            ET.ElementTree(manifest).write(cls.decoded / "AndroidManifest.xml",
                                           encoding="utf-8", xml_declaration=True)

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
        styles = ET.parse(self.decoded / "res/values/styles.xml").getroot()
        settings = styles.find("style[@name='Theme.Ha9_comp_service.Settings']")
        self.assertEqual(settings.get("parent"), "@style/Theme.Material3.DayNight.NoActionBar")
        night_styles = ET.parse(
            self.decoded / "res/values-night/styles.xml"
        ).getroot()
        night_settings = night_styles.find("style[@name='Theme.Ha9_comp_service.Settings']")
        self.assertIsNotNone(night_settings)
        service = (self.decoded /
                   "smali/com/lmqr/ha9_comp_service/A9AccessibilityService.smali").read_text()
        self.assertNotIn('const-string v9, "disable_show_per_app_aod_settings"', service)
        self.assertIn("getStaticAodLinearLayout()", service)
        self.assertIn("cameraLiveRefresh:Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;", service)

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
        self.assertIn("move-object v12, p1", action_manager)
        self.assertEqual(action_manager.count(
            "invoke-direct {v0, v12, p2}, "
            "Lcom/lmqr/ha9_comp_service/button_mapper/DpadButtonAction;-><init>"), 4)
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
        accessor = (smali / "FloatingMenuViewAccessor.smali").read_text()
        self.assertIn("getVideoOptimizedRefresh()Landroid/widget/Switch;", accessor)
        toggle_setup = (smali / "VideoRefreshSwitchSetup.smali").read_text()
        self.assertIn("setupVideoRefreshSwitch", toggle_setup)
        controls = (smali / "DisplaySettingsManager.smali").read_text()
        self.assertIn('"display:"', controls)
        self.assertNotIn("disable_perapprefresh", controls)
        self.assertIn("setOnCheckedChangeListener", controls)
        launch_settings = (smali / "AppLaunchSettings.smali").read_text()
        self.assertIn("queryIntentActivities", launch_settings)
        self.assertNotIn('"Apps to launch with side keys"', launch_settings)
        self.assertIn('"Launch App"', launch_settings)
        for preference_class in ("ListPreference",):
            self.assertNotIn(
                f"Landroidx/preference/{preference_class};-><init>(Landroid/content/Context;)V",
                launch_settings,
            )
            self.assertIn(
                f"Landroidx/preference/{preference_class};-><init>"
                "(Landroid/content/Context;Landroid/util/AttributeSet;)V",
                launch_settings,
            )
        for preference_class, method in (
                ("DialogPreference", "setDialogTitle(Ljava/lang/CharSequence;)V"),
                ("Preference", "setEnabled(Z)V")):
            preference_source = (
                self.decoded / f"smali/androidx/preference/{preference_class}.smali"
            ).read_text()
            self.assertIn(f".method public {method}", preference_source)
        preference_source = (
            self.decoded / "smali/androidx/preference/Preference.smali"
        ).read_text()
        self.assertIn(".method public final setVisible(Z)V", preference_source)
        self.assertIn(
            "->onPreferenceChange(Landroidx/preference/Preference;Ljava/lang/Object;)Z",
            preference_source,
        )
        binding = (smali / "AppLaunchPreferenceBinding.smali").read_text()
        self.assertIn("->setVisible(Z)V", binding)
        self.assertIn('"Choose an app to launch"', binding)
        self.assertIn("->getParent()", launch_settings)
        self.assertIn("->setOrder(I)V", launch_settings)
        launch_action = (smali / "button_mapper/LaunchAppButtonAction.smali").read_text()
        self.assertIn("->getLaunchIntentForPackage", launch_action)
        self.assertIn("->startActivity", launch_action)
        self.assertIn(":activity_not_found", launch_action)
        self.assertIn(":security_exception", launch_action)
        self.assertIn("PowerManager;->isInteractive()", launch_action)
        self.assertIn("PowerManager$WakeLock;->acquire(J)V", launch_action)
        self.assertNotIn("->setLayoutResource", launch_settings)
        action_manager = (smali / "button_mapper/ButtonActionManager.smali").read_text()
        action_map = (smali / "button_mapper/AppLaunchActionMap.smali").read_text()
        self.assertIn("AppLaunchActionMap;->addToMap", action_manager)
        for preference_key in (
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
                "long_press_eink_action_screen_off"):
            self.assertIn(f'"launch_app_{preference_key}"', action_map)
            self.assertIn(f'"launch_app_package_{preference_key}"', action_map)
        manifest = ET.parse(self.decoded / "AndroidManifest.xml").getroot()
        launcher_query = next((
            intent for intent in manifest.findall("queries/intent")
            if intent.find(f"action[@{ANDROID}name='android.intent.action.MAIN']") is not None
        ), None)
        self.assertIsNotNone(launcher_query)
        self.assertIsNotNone(launcher_query.find(
            f"category[@{ANDROID}name='android.intent.category.LAUNCHER']"))
        app_event = (smali / "A9AccessibilityService$onAccessibilityEvent$1.smali").read_text()
        self.assertIn("->onDisplayAppChange", app_event)
        camera_refresh = (smali / "CameraLiveRefresh.smali").read_text()
        self.assertIn("setScreenOn(Z)V", camera_refresh)
        self.assertIn("setVideoOptimized(Z)V", camera_refresh)
        self.assertIn("->removeCallbacks", camera_refresh)
        key_event = (smali / "A9AccessibilityService.smali").read_text()
        self.assertIn(":forward_other_key", key_event)
        self.assertIn("ScreenOffKeyReceiver;->onKeyEvent", key_event)
        self.assertIn("ScreenOffKeyReceiver;->close()", key_event)
        key_bridge = (smali / "ScreenOffKeyReceiver.smali").read_text()
        self.assertIn("getScanCode()I", key_bridge)
        self.assertIn('"android.permission.INJECT_EVENTS"', key_bridge)
        self.assertIn("PowerManager;->isInteractive()", key_bridge)
        self.assertIn("->dispatchSideKey(IIJ)V", key_bridge)
        for suffix in ("", "Top"):
            listener = (smali / f"A9AccessibilityService$hardwareGestureDetector{suffix}$1.smali").read_text()
            self.assertEqual(listener.count("->isSideKeyScreenOn(I)Z"), 3)
            self.assertNotIn("->access$isScreenOn$p", listener)
        self.assertIn("VideoRefreshSwitchSetup;->setup", key_event)
        service_method = key_event.split(
            ".method public final setVideoOptimizedRefresh(Z)V", 1)[1]
        self.assertIn("CameraLiveRefresh;->setVideoOptimized(Z)V", service_method)
        screen_receiver = (smali / "A9AccessibilityService$receiver$1.smali").read_text()
        self.assertIn("invoke-virtual {p1, p2}, "
                      "Lcom/lmqr/ha9_comp_service/A9AccessibilityService;"
                      "->setLiveRefreshScreenOn(Z)V", screen_receiver)
        self.assertIn("invoke-virtual {p1, v4}, "
                      "Lcom/lmqr/ha9_comp_service/A9AccessibilityService;"
                      "->setLiveRefreshScreenOn(Z)V", screen_receiver)
        self.assertNotIn("->cameraLiveRefresh:", screen_receiver)
        layout = ET.parse(self.decoded / "res/layout/floating_menu_layout.xml").getroot()
        toggle = next(node for node in layout.iter()
                      if node.get("{http://schemas.android.com/apk/res/android}id")
                      == "@id/video_optimized_refresh")
        self.assertEqual(toggle.tag, "Switch")
        self.assertEqual(toggle.get("{http://schemas.android.com/apk/res/android}text"),
                         "Video refresh (experimental)")
        self.run_command("java", "-jar", self.apktool, "b", self.decoded,
                         "-o", self.work / "settings.apk")
        self.assertTrue((self.work / "settings.apk").is_file())
        if os.environ.get("HIBREAK_ADB_TESTS") == "1":
            signer = Path(os.environ.get("APK_SIGNER_JAR", ROOT / "local/uber-apk-signer.jar"))
            self.run_command("java", "-jar", signer, "-a", self.work / "settings.apk",
                             "-o", self.work / "signed")
            installed = False
            try:
                self.run_command("adb", "install", "-t",
                                 self.work / "signed/settings-aligned-debugSigned.apk")
                installed = True
                result = subprocess.run(
                    ["adb", "shell", "am", "instrument", "-w",
                     self.test_package + "/hibreak.tests.RuntimeInstrumentation"],
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("PASS: DPAD dispatch, popup inflation and switch setup, "
                              "screen off/on receiver, settings startup and 12 app-launch pickers",
                              result.stdout)
                self.run_command("adb", "shell", "appops", "set", self.test_package,
                                 "SYSTEM_ALERT_WINDOW", "allow")
                monitor = None
                monitor_pid = None
                device_monitor = "/data/local/tmp/" + self.test_package
                try:
                    physical = os.environ.get("HIBREAK_PHYSICAL_KEY_TESTS") == "1"
                    if physical:
                        ndk = Path(os.environ["ANDROID_NDK_HOME"])
                        compiler = (ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin/"
                                    "aarch64-linux-android30-clang")
                        binary = self.work / "side-key-monitor"
                        self.run_command(
                            compiler, "-O2", "-Wall", "-Wextra", "-Werror",
                            f'-DSIDE_KEY_PACKAGE="{self.test_package}"',
                            ROOT / "tools/tests/native/SideKeyMonitorProbe.c",
                            ROOT / "a9_eink_daemon/side_keys.c", "-llog", "-o", binary)
                        self.run_command("adb", "push", binary, device_monitor)
                        self.run_command("adb", "shell", "chmod", "700", device_monitor)
                        monitor = subprocess.Popen(
                            ["adb", "shell", "echo $$; exec " + device_monitor],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                        monitor_pid = monitor.stdout.readline().strip()
                        self.assertTrue(monitor_pid.isdigit(), monitor_pid)
                    self.run_command("adb", "shell", "input", "keyevent", "223")
                    arguments = ["-e", "physical_test", "1"] if physical else []
                    if physical:
                        print("Press the TOP side key ONCE with the display asleep now.",
                              flush=True)
                    result = subprocess.run(
                        ["adb", "shell", "am", "instrument", "-w", "-e", "wake_test", "1",
                         *arguments,
                         self.test_package + "/hibreak.tests.RuntimeInstrumentation"],
                        capture_output=True, text=True, timeout=75 if physical else 30)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("PASS: screen-off app launch wakes display", result.stdout)
                finally:
                    if monitor_pid is not None and monitor_pid.isdigit():
                        self.run_command("adb", "shell", "kill", monitor_pid)
                    if monitor is not None:
                        monitor.communicate(timeout=10)
                        self.run_command("adb", "shell", "rm", device_monitor)
                    self.run_command("adb", "shell", "input", "keyevent", "224")
            finally:
                if installed:
                    self.run_command("adb", "uninstall", self.test_package)
