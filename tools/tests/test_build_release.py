import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("build_release", ROOT / "tools/build-release.py")
assert SPEC is not None and SPEC.loader is not None
build_release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_release)


class ReleaseBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="release-build-test-")
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        environment = mock.patch.dict(build_release.os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        for name in ("VENDOR", "AOSP_HEADERS", "ANDROID_NDK_HOME", "SECILC",
                     "APK_RELEASE_CERT_SHA256", "APK_SIGNER_JAR"):
            build_release.os.environ.pop(name, None)
        self.gsi = self.work / "input.img"
        self.apk = self.work / "base.apk"
        self.vendor = self.work / "vendor.img"
        self.headers = self.work / "headers"
        self.gsi.write_bytes(b"gsi")
        self.apk.write_bytes(b"apk")
        self.vendor.write_bytes(b"vendor")
        (self.headers / "hardware").mkdir(parents=True)
        (self.headers / "hardware/consumerir.h").write_text("consumerir")
        (self.headers / "hardware/hardware.h").write_text("hardware")

    def fake_build(self, commands):
        def run(command, **_kwargs):
            commands.append(command)
            if command[0] == "bash" and command[1].endswith("build-source-apk.sh"):
                output = Path(command[2])
            elif command[0] == "bash" and command[1].endswith("build-daemon.sh"):
                output = Path(command[2])
            elif command[0] == "bash" and command[1].endswith("patch-gsi.sh"):
                output = Path(command[3])
            elif command[0] == "bash" and command[1].endswith("build-ir-hal.sh"):
                output = Path(command[2])
            else:
                output = Path(command[3])
            output.write_bytes(b"built:" + output.name.encode())
            return subprocess.CompletedProcess(command, 0)
        return run

    def test_builds_requested_stages_and_records_manifest(self):
        output_root = self.work / "builds"
        commands = []
        with mock.patch.object(sys, "argv", [
            "build-release.py", str(self.gsi),
            "--vendor-image", str(self.vendor),
            "--aosp-headers", str(self.headers),
            "--ir", "--xrz", "--output-root", str(output_root),
        ]), mock.patch.object(subprocess, "run", side_effect=self.fake_build(commands)):
            build_release.main()

        self.assertEqual(len(commands), 6)
        self.assertTrue(commands[0][1].endswith("build-source-apk.sh"))
        self.assertTrue(commands[1][1].endswith("build-daemon.sh"))
        self.assertTrue(commands[2][1].endswith("patch-gsi.sh"))
        self.assertTrue(commands[3][1].endswith("build-ir-hal.sh"))
        self.assertTrue(commands[4][1].endswith("add-ir-capture-to-gsi.py"))
        self.assertTrue(commands[5][1].endswith("add-xrz-compat-to-gsi.py"))
        self.assertIn("--release", commands[2])
        self.assertIn("--hal-module", commands[4])
        self.assertEqual(commands[4][commands[4].index("--vendor-image") + 1], str(self.vendor))
        build_dir = next(output_root.iterdir())
        manifest = json.loads((build_dir / "manifest.json").read_text())
        self.assertEqual(manifest["options"], {
            "ir": True, "xrz_v2": True, "release": True, "source_apk": True,
        })
        self.assertEqual(Path(manifest["final_image"]).name, "HiBreakPro-xrz-v2-test.img")
        self.assertEqual(manifest["inputs"]["gsi"]["sha256"], build_release.sha256(self.gsi))
        self.assertIn("HiBreakPro-release-base.img", manifest["outputs"])
        self.assertIn("HiBreakPro-release-ir.img", manifest["outputs"])
        self.assertIn("HiBreakPro-xrz-v2-test.img", manifest["outputs"])
        self.assertEqual(commands[4][1], str(ROOT / "tools/add-ir-capture-to-gsi.py"))

    def test_explicit_source_apk_records_source_inputs(self):
        output_root = self.work / "source-builds"
        commands = []
        with mock.patch.object(sys, "argv", [
            "build-release.py", str(self.gsi), "--source-apk",
            "--output-root", str(output_root),
        ]), mock.patch.object(subprocess, "run", side_effect=self.fake_build(commands)):
            build_release.main()

        self.assertEqual(len(commands), 3)
        self.assertTrue(commands[0][1].endswith("build-source-apk.sh"))
        manifest = json.loads((next(output_root.iterdir()) / "manifest.json").read_text())
        self.assertTrue(manifest["options"]["source_apk"])
        self.assertNotIn("base_apk", manifest["inputs"])
        source = ROOT / "a9_accessibility_service/src/com/lmqr/ha9_comp_service/BootReceiver.kt"
        key = f"apk_source:{source.relative_to(ROOT)}"
        self.assertEqual(manifest["inputs"][key]["sha256"], build_release.sha256(source))
        for path in ("settings.gradle.kts", "a9_accessibility_service/build.gradle.kts",
                     "a9_accessibility_service/standalone/AndroidManifest.xml",
                     "tools/android-system-api-stubs/src/main/java/android/os/SystemProperties.java"):
            self.assertIn(f"apk_source:{path}", manifest["inputs"])

    def test_exactly_one_apk_source_is_required_before_creating_build_directory(self):
        for extra in ([str(self.apk)], [str(self.apk), "--source-apk"],
                      [str(self.apk), "--built-apk", str(self.apk)],
                      ["--source-apk", "--built-apk", str(self.apk)]):
            with self.subTest(extra=extra):
                output_root = self.work / "unused-builds"
                with mock.patch.object(sys, "argv", [
                    "build-release.py", str(self.gsi), *extra,
                    "--output-root", str(output_root),
                ]), self.assertRaises(SystemExit) as result:
                    build_release.main()
                self.assertEqual(result.exception.code, 2)
                self.assertFalse(output_root.exists())

    def test_default_builds_source_apk(self):
        commands = []
        with mock.patch.object(sys, "argv", [
            "build-release.py", str(self.gsi), "--output-root", str(self.work / "default"),
        ]), mock.patch.object(subprocess, "run", side_effect=self.fake_build(commands)):
            build_release.main()
        self.assertTrue(commands[0][1].endswith("build-source-apk.sh"))

    def test_default_automates_all_stages_with_environment_inputs(self):
        commands = []
        environments = []
        build = self.fake_build(commands)

        def run(command, env, **kwargs):
            environments.append(env)
            return build(command, **kwargs)

        with mock.patch.dict(build_release.os.environ, {
            "VENDOR": str(self.vendor), "AOSP_HEADERS": str(self.headers),
            "ANDROID_NDK_HOME": str(self.work / "ndk"), "SECILC": "/custom/secilc",
        }), mock.patch.object(sys, "argv", [
            "build-release.py", str(self.gsi), "--ir", "--xrz",
            "--output-root", str(self.work / "all-stages"),
        ]), mock.patch.object(subprocess, "run", side_effect=run):
            build_release.main()
        self.assertEqual(len(commands), 6)
        self.assertTrue(commands[0][1].endswith("build-source-apk.sh"))
        for command in commands[-2:]:
            self.assertEqual(command[command.index("--secilc") + 1], "/custom/secilc")
            self.assertEqual(command[command.index("--vendor-image") + 1], str(self.vendor))
        self.assertEqual(environments[0]["AOSP_HEADERS"], str(self.headers))
        self.assertEqual(environments[0]["ANDROID_NDK_HOME"], str(self.work / "ndk"))
        self.assertEqual(commands[-1][2], commands[-2][3])

    def test_reuses_signed_apk_and_passes_overlay_tools(self):
        commands = []
        environments = []
        build = self.fake_build(commands)

        def run(command, env, **kwargs):
            environments.append(env)
            if command[0] == "java":
                commands.append(command)
                return subprocess.CompletedProcess(command, 0)
            return build(command, **kwargs)

        signer = self.work / "signer.jar"
        signer.write_bytes(b"signer")
        output_root = self.work / "reuse"
        with mock.patch.dict(build_release.os.environ, {
            "APK_SIGNER_JAR": str(signer), "APK_RELEASE_CERT_SHA256": "AB:" * 31 + "AB",
        }), mock.patch.object(sys, "argv", [
            "build-release.py", str(self.gsi), "--built-apk", str(self.apk),
            "--ir", "--xrz", "--vendor-image", str(self.vendor),
            "--aosp-headers", str(self.headers), "--ndk", str(self.work / "ndk"),
            "--secilc", "/custom/secilc", "--output-root", str(output_root),
        ]), mock.patch.object(subprocess, "run", side_effect=run):
            build_release.main()
        self.assertIn("--onlyVerify", commands[0])
        self.assertIn("AB" * 32, commands[0])
        self.assertFalse(any("build-source-apk.sh" in arg
                             for command in commands for arg in command))
        for command in commands[-2:]:
            self.assertEqual(command[command.index("--secilc") + 1], "/custom/secilc")
        self.assertEqual(environments[0]["ANDROID_NDK_HOME"], str(self.work / "ndk"))
        directory = next(output_root.iterdir())
        self.assertEqual((directory / "HiBreakEink-release.apk").read_bytes(), b"apk")
        manifest = json.loads((directory / "manifest.json").read_text())
        self.assertTrue(manifest["options"]["reuse_built_apk"])
        self.assertEqual(manifest["inputs"]["built_apk"]["sha256"], build_release.sha256(self.apk))

    def test_failed_apk_verification_stops_before_image_build(self):
        signer = self.work / "signer.jar"
        signer.write_bytes(b"signer")
        with mock.patch.dict(build_release.os.environ, {"APK_SIGNER_JAR": str(signer)}), \
                mock.patch.object(sys, "argv", [
                    "build-release.py", str(self.gsi), "--built-apk", str(self.apk),
                    "--output-root", str(self.work / "failed"),
                ]), mock.patch.object(subprocess, "run",
                                      side_effect=subprocess.CalledProcessError(1, ["java"])) as run, \
                self.assertRaises(SystemExit):
            build_release.main()
        self.assertEqual(run.call_count, 1)

    def test_bad_built_apk_inputs_fail_before_creating_build_directory(self):
        for path, fingerprint in ((self.work / "missing.apk", ""),
                                  (self.apk, "invalid")):
            with self.subTest(path=path, fingerprint=fingerprint):
                output = self.work / "unused"
                with mock.patch.dict(build_release.os.environ, {
                    "APK_RELEASE_CERT_SHA256": fingerprint,
                }), mock.patch.object(sys, "argv", [
                    "build-release.py", str(self.gsi), "--built-apk", str(path),
                    "--output-root", str(output),
                ]), self.assertRaises(SystemExit) as result:
                    build_release.main()
                self.assertEqual(result.exception.code, 2)
                self.assertFalse(output.exists())

    def test_ir_header_path_is_passed_to_build_command_environment(self):
        output_root = self.work / "builds"
        environments = []
        commands = []
        build = self.fake_build(commands)

        def run(command, env, **_kwargs):
            environments.append(env)
            return build(command)

        with mock.patch.object(sys, "argv", [
            "build-release.py", str(self.gsi),
            "--vendor-image", str(self.vendor), "--aosp-headers", str(self.headers),
            "--ir", "--output-root", str(output_root),
        ]), mock.patch.object(subprocess, "run", side_effect=run):
            build_release.main()
        self.assertEqual(environments[0]["AOSP_HEADERS"], str(self.headers.resolve()))

    def test_ir_requires_vendor_and_headers_before_creating_build_directory(self):
        output_root = self.work / "unused-builds"
        with mock.patch.object(sys, "argv", [
            "build-release.py", str(self.gsi),
            "--ir", "--output-root", str(output_root),
        ]), self.assertRaises(SystemExit) as result:
            build_release.main()
        self.assertEqual(result.exception.code, 2)
        self.assertFalse(output_root.exists())


if __name__ == "__main__":
    unittest.main()
