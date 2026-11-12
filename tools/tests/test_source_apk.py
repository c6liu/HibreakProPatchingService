import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
ANDROID = "{http://schemas.android.com/apk/res/android}"
APP = "{http://schemas.android.com/apk/res-auto}"


class SourceApkBuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="source-apk-test-")
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.bin = self.work / "bin"
        self.bin.mkdir()
        self.log = self.work / "calls.jsonl"
        self.output = self.work / "signed output.apk"
        self.signer = self.work / "signer.jar"
        self.signer.write_bytes(b"signer")
        self.env = os.environ.copy()
        for name in ("APK_RELEASE_KEYSTORE", "APK_RELEASE_KEY_ALIAS",
                     "APK_RELEASE_CERT_SHA256", "HIBREAK_FAKE_SIGNER_FAIL",
                     "HIBREAK_FAKE_COMPETING_OUTPUT"):
            self.env.pop(name, None)
        self.env.update({
            "PATH": str(self.bin) + os.pathsep + self.env["PATH"],
            "APK_SIGNER_JAR": str(self.signer),
            "HIBREAK_FAKE_LOG": str(self.log),
        })
        self.write_tool("gradle", """\
#!/usr/bin/env python3
import json, os, pathlib, sys
with open(os.environ["HIBREAK_FAKE_LOG"], "a") as log:
    log.write(json.dumps(["gradle", *sys.argv[1:]]) + "\\n")
build = next(arg.split("=", 1)[1] for arg in sys.argv if arg.startswith("-PhibreakBuildDir="))
output = pathlib.Path(build) / "gradle/app/outputs/apk/release/app-release-unsigned.apk"
output.parent.mkdir(parents=True)
output.write_bytes(b"unsigned")
""")
        self.write_tool("java", """\
#!/usr/bin/env python3
import json, os, pathlib, sys
with open(os.environ["HIBREAK_FAKE_LOG"], "a") as log:
    log.write(json.dumps(["java", *sys.argv[1:]]) + "\\n")
if os.environ.get("HIBREAK_FAKE_SIGNER_FAIL") == "1":
    sys.exit(7)
if os.environ.get("HIBREAK_FAKE_COMPETING_OUTPUT"):
    pathlib.Path(os.environ["HIBREAK_FAKE_COMPETING_OUTPUT"]).write_bytes(b"competing")
output = pathlib.Path(sys.argv[sys.argv.index("-o") + 1])
output.mkdir(parents=True)
(output / "signed.apk").write_bytes(b"signed")
""")

    def write_tool(self, name, content):
        path = self.bin / name
        path.write_text(content)
        path.chmod(0o755)

    def build(self):
        return subprocess.run(
            ["bash", ROOT / "tools/build/build-source-apk.sh", self.output],
            env=self.env, capture_output=True, text=True,
        )

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_builds_in_an_isolated_directory_and_uses_debug_signing(self):
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.output.read_bytes(), b"signed")
        gradle, signer = self.calls()
        build_arg = next(arg for arg in gradle if arg.startswith("-PhibreakBuildDir="))
        self.assertFalse(Path(build_arg.split("=", 1)[1]).parent.exists())
        self.assertIn("--project-cache-dir", gradle)
        self.assertIn(":app:assembleRelease", gradle)
        self.assertNotIn("--ks", signer)
        self.assertNotIn("--ksPass", signer)

    def test_release_signing_checks_and_passes_the_expected_fingerprint(self):
        keystore = self.work / "key.jks"
        keystore.write_bytes(b"keystore")
        self.env.update({
            "APK_RELEASE_KEYSTORE": str(keystore),
            "APK_RELEASE_KEY_ALIAS": "test-key",
            "APK_RELEASE_CERT_SHA256": ":".join(["AB"] * 32),
        })
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        signer = self.calls()[1]
        self.assertEqual(signer[signer.index("--ks") + 1], str(keystore))
        self.assertEqual(signer[signer.index("--ksAlias") + 1], "test-key")
        self.assertEqual(signer[signer.index("--verifySha256") + 1], "AB" * 32)
        self.assertNotIn("--ksPass", signer)
        self.assertNotIn("--ksKeyPass", signer)

    def test_incomplete_or_invalid_signing_fails_before_building(self):
        self.env["APK_RELEASE_KEY_ALIAS"] = "test-key"
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set APK_RELEASE_KEYSTORE", result.stderr)
        self.assertFalse(self.log.exists())
        keystore = self.work / "key.jks"
        keystore.write_bytes(b"keystore")
        self.env.update({"APK_RELEASE_KEYSTORE": str(keystore),
                         "APK_RELEASE_CERT_SHA256": "bad-fingerprint"})
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("64-digit SHA-256", result.stderr)
        self.assertFalse(self.log.exists())

    def test_existing_or_symlink_output_is_not_overwritten(self):
        self.output.write_bytes(b"existing")
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing to overwrite", result.stderr)
        self.assertEqual(self.output.read_bytes(), b"existing")
        self.output.unlink()
        self.output.symlink_to(self.work / "missing-target")
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing to overwrite", result.stderr)
        self.assertTrue(self.output.is_symlink())
        self.assertFalse(self.log.exists())

    def test_signing_failure_does_not_create_an_output(self):
        self.env["HIBREAK_FAKE_SIGNER_FAIL"] = "1"
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output.exists())

    def test_output_created_during_signing_is_not_overwritten(self):
        self.env["HIBREAK_FAKE_COMPETING_OUTPUT"] = str(self.output)
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("without overwriting", result.stderr)
        self.assertEqual(self.output.read_bytes(), b"competing")


class SourceApkArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        value = os.environ.get("HIBREAK_SOURCE_APK")
        if not value:
            raise unittest.SkipTest("Set HIBREAK_SOURCE_APK to inspect a source-built APK")
        cls.apk = Path(value).resolve()
        apktool = Path(os.environ.get("APKTOOL_JAR", ROOT / "local/apktool.jar"))
        sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
        if not cls.apk.is_file() or not apktool.is_file() or not sdk:
            raise AssertionError("Source APK, apktool and ANDROID_HOME/ANDROID_SDK_ROOT are required")
        if not shutil.which("java"):
            raise AssertionError("Java is required to inspect the source APK")
        cls.aapt = Path(sdk) / "build-tools/36.0.0/aapt2"
        cls.apksigner = Path(sdk) / "build-tools/36.0.0/apksigner"
        cls.tmp = tempfile.TemporaryDirectory(prefix="source-apk-artifact-test-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.decoded = Path(cls.tmp.name) / "decoded"
        subprocess.run(["java", "-jar", apktool, "d", cls.apk, "-o", cls.decoded],
                       check=True, capture_output=True, text=True)
        cls.manifest = ET.parse(cls.decoded / "AndroidManifest.xml").getroot()

    def test_manifest_preserves_privileged_boot_contract(self):
        self.assertEqual(self.manifest.get("package"), "com.lmqr.ha9_comp_service")
        self.assertNotIn(ANDROID + "sharedUserId", self.manifest.attrib)
        application = self.manifest.find("application")
        if application is None:
            raise AssertionError("APK manifest has no application")
        self.assertEqual(application.get(ANDROID + "usesNonSdkApi"), "true")
        self.assertEqual(application.get(ANDROID + "directBootAware"), "true")
        self.assertEqual(application.get(ANDROID + "defaultToDeviceProtectedStorage"), "true")
        self.assertEqual(application.get(ANDROID + "persistent"), "true")
        required_permissions = {
            "android.permission.WRITE_SECURE_SETTINGS",
            "android.permission.RECEIVE_BOOT_COMPLETED",
            "android.permission.QUERY_ALL_PACKAGES",
            "android.permission.WAKE_LOCK",
            "android.permission.TURN_SCREEN_ON",
        }
        actual = {node.get(ANDROID + "name") for node in self.manifest.findall("uses-permission")}
        self.assertTrue(required_permissions <= actual)
        components = {node.get(ANDROID + "name") for node in application
                      if node.tag in ("activity", "service", "receiver")}
        for name in ("SettingsActivity", "A9AccessibilityService", "BootReceiver",
                     "ActionTargetPickerActivity",
                     "quick_settings.LaunchSettingsTile", "quick_settings.ClearScreenTile"):
            self.assertIn(f"com.lmqr.ha9_comp_service.{name}", components)
        picker = next(node for node in application.findall("activity")
                      if node.get(ANDROID + "name", "").endswith(".ActionTargetPickerActivity"))
        self.assertEqual(picker.get(ANDROID + "exported"), "false")
        receiver = next(node for node in application.findall("receiver")
                        if node.get(ANDROID + "name", "").endswith(".BootReceiver"))
        actions = {node.get(ANDROID + "name") for node in receiver.findall("intent-filter/action")}
        self.assertTrue({"android.intent.action.BOOT_COMPLETED",
                         "android.intent.action.LOCKED_BOOT_COMPLETED",
                         "android.intent.action.MY_PACKAGE_REPLACED"} <= actions)

    def test_compiled_dex_uses_the_system_api_without_packaging_the_stub(self):
        boot = list(self.decoded.glob("smali*/com/lmqr/ha9_comp_service/BootReceiver.smali"))
        self.assertEqual(len(boot), 1)
        self.assertIn("Landroid/os/SystemProperties;->get(Ljava/lang/String;"
                      "Ljava/lang/String;)Ljava/lang/String;", boot[0].read_text())
        self.assertFalse(list(self.decoded.glob("smali*/android/os/SystemProperties.smali")))
        for name in ("A9AccessibilityService", "SettingsActivity", "AppLaunchSettings",
                     "PerAppRefreshPreference", "CameraLiveRefresh", "ActionTargetPickerActivity",
                     "ShortcutAssignment", "ButtonActionSettings"):
            self.assertEqual(len(list(self.decoded.glob(
                f"smali*/com/lmqr/ha9_comp_service/{name}.smali"))), 1)
        service = next(self.decoded.glob(
            "smali*/com/lmqr/ha9_comp_service/A9AccessibilityService.smali")).read_text()
        self.assertIn('"camera_live_refresh"', service)
        self.assertIn("CameraLiveRefresh;->update()V", service)

    def test_preferences_are_packaged_with_the_expected_defaults(self):
        root = ET.parse(self.decoded / "res/xml/root_preferences.xml").getroot()
        keyed = {node.get(APP + "key"): node for node in root.iter() if node.get(APP + "key")}
        source = ET.parse(ROOT / "a9_accessibility_service/res/xml/root_preferences.xml").getroot()
        expected = {node.get(APP + "key"): node for node in source.iter() if node.get(APP + "key")}
        self.assertEqual(set(keyed), set(expected))
        for key in expected:
            self.assertEqual(keyed[key].tag, expected[key].tag)
            self.assertEqual(keyed[key].attrib, expected[key].attrib)
        self.assertEqual(sum(node.get(APP + "key") == "camera_live_refresh"
                             for node in root.iter()), 1)
        self.assertEqual(keyed["refresh_setting"].get(APP + "defaultValue"), "1")
        self.assertEqual(keyed["camera_live_refresh"].get(APP + "defaultValue"), "true")
        self.assertIn("per_app_refresh_modes", keyed)
        self.assertIn("allow_custom_broadcast", keyed)
        self.assertNotIn("disable_show_per_app_aod_settings", keyed)

    def test_version_and_signature_are_valid(self):
        badging = subprocess.run([self.aapt, "dump", "badging", self.apk],
                                 check=True, capture_output=True, text=True).stdout
        self.assertIn("name='com.lmqr.ha9_comp_service'", badging)
        self.assertIn("versionCode='35'", badging)
        self.assertIn("versionName='15'", badging)
        self.assertIn("minSdkVersion:'35'", badging)
        self.assertIn("targetSdkVersion:'35'", badging)
        verification = subprocess.run([self.apksigner, "verify", "--print-certs", self.apk],
                                      check=True, capture_output=True, text=True).stdout
        self.assertIn("Signer #1 certificate SHA-256 digest:", verification)




if __name__ == "__main__":
    unittest.main()
