import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
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
            if Path(command[1]).name in ("add-eink-init-bridge-to-gsi.py", "add-eink-migration-to-gsi.py"):
                daemon = next(Path(item[2]) for item in commands if Path(item[1]).name == "build-daemon.sh")
                output.with_name(output.name + ".manifest.json").write_text(json.dumps({
                    "daemon_sha256": build_release.sha256(daemon),
                }))
            return subprocess.CompletedProcess(command, 0)
        return run

    def test_builds_requested_stages_and_records_manifest(self):
        output_root = self.work / "builds"
        commands = []
        with mock.patch.object(sys, "argv", [
            "build-release.py", str(self.gsi), "--compatibility",
            "--vendor-image", str(self.vendor),
            "--aosp-headers", str(self.headers),
            "--ir", "--xrz", "--output-root", str(output_root),
        ]), mock.patch.object(subprocess, "run", side_effect=self.fake_build(commands)):
            build_release.main()

        self.assertEqual(len(commands), 6)
        command_names = [Path(command[1]).name for command in commands]
        daemon_command = next(command for command in commands
                              if Path(command[1]).name == "build-daemon.sh")
        self.assertNotIn("--experimental-property-only-refresh", daemon_command)
        self.assertNotIn("--experimental-property-only-auto-refresh", daemon_command)
        self.assertCountEqual(command_names[:3], [
            "build-source-apk.sh", "build-daemon.sh", "build-ir-hal.sh",
        ])
        self.assertEqual(command_names[3:], [
            "patch-gsi.sh", "add-ir-capture-to-gsi.py", "add-xrz-compat-to-gsi.py",
        ])
        patch_command, ir_command, _xrz_command = commands[3:]
        self.assertIn("--release", patch_command)
        self.assertIn("--hal-module", ir_command)
        self.assertEqual(ir_command[ir_command.index("--vendor-image") + 1], str(self.vendor))
        build_dir = next(output_root.iterdir())
        manifest = json.loads((build_dir / "manifest.json").read_text())
        self.assertEqual(manifest["options"], {
            "ir": True, "xrz_v2": True, "release": True, "source_apk": True,
            "reuse_built_apk": False, "experimental_property_only_refresh": False,
            "experimental_property_only_auto_refresh": False, "experimental_phh_reduction": False,
            "init_eink_bridge": False, "enforcing_eink_and_display": False,
        })
        self.assertEqual(Path(manifest["final_image"]).name, "HiBreakPro-release.img")
        self.assertEqual(manifest["inputs"]["gsi"]["sha256"], build_release.sha256(self.gsi))
        self.assertIn("HiBreakPro-release.img", manifest["outputs"])
        self.assertNotIn("HiBreakPro-release-base.img", manifest["outputs"])
        self.assertNotIn("HiBreakPro-release-ir.img", manifest["outputs"])
        self.assertNotIn("HiBreakPro-xrz-v2-test.img", manifest["outputs"])
        self.assertTrue((build_dir / "HiBreakPro-release.img").is_file())
        self.assertEqual([path.name for path in build_dir.glob("*.img")],
                         ["HiBreakPro-release.img"])
        self.assertFalse(any(build_dir.glob(".release-stages-*")))
        self.assertEqual(ir_command[1], str(ROOT / "tools/add-ir-capture-to-gsi.py"))

    def test_property_only_refresh_is_opt_in_and_recorded(self):
        output_root = self.work / "property-only-builds"
        commands = []
        with mock.patch.object(sys, "argv", [
            "build-release.py", str(self.gsi), "--compatibility", "--experimental-property-only-refresh",
            "--output-root", str(output_root),
        ]), mock.patch.object(subprocess, "run", side_effect=self.fake_build(commands)):
            build_release.main()
        daemon_command = next(command for command in commands
                              if Path(command[1]).name == "build-daemon.sh")
        self.assertEqual(daemon_command[3:], ["--experimental-property-only-refresh"])
        manifest = json.loads((next(output_root.iterdir()) / "manifest.json").read_text())
        self.assertTrue(manifest["options"]["experimental_property_only_refresh"])

    def test_property_only_auto_refresh_combines_and_is_recorded(self):
        output_root = self.work / "auto-refresh-builds"
        commands = []
        with mock.patch.object(sys, "argv", [
            "build-release.py", str(self.gsi), "--compatibility", "--experimental-property-only-refresh",
            "--experimental-property-only-auto-refresh", "--output-root", str(output_root),
        ]), mock.patch.object(subprocess, "run", side_effect=self.fake_build(commands)):
            build_release.main()
        daemon_command = next(command for command in commands
                              if Path(command[1]).name == "build-daemon.sh")
        self.assertEqual(daemon_command[3:], [
            "--experimental-property-only-refresh",
            "--experimental-property-only-auto-refresh",
        ])
        manifest = json.loads((next(output_root.iterdir()) / "manifest.json").read_text())
        self.assertTrue(manifest["options"]["experimental_property_only_refresh"])
        self.assertTrue(manifest["options"]["experimental_property_only_auto_refresh"])

    def test_explicit_source_apk_records_source_inputs(self):
        output_root = self.work / "source-builds"
        commands = []
        with mock.patch.object(sys, "argv", [
            "build-release.py", str(self.gsi), "--compatibility", "--source-apk",
            "--output-root", str(output_root),
        ]), mock.patch.object(subprocess, "run", side_effect=self.fake_build(commands)):
            build_release.main()

        self.assertEqual(len(commands), 3)
        self.assertIn("build-source-apk.sh", [Path(command[1]).name for command in commands[:2]])
        build_dir = next(output_root.iterdir())
        manifest = json.loads((build_dir / "manifest.json").read_text())
        self.assertEqual(Path(manifest["final_image"]).name, "HiBreakPro-release.img")
        self.assertEqual([path.name for path in build_dir.glob("*.img")],
                         ["HiBreakPro-release.img"])
        self.assertTrue(manifest["options"]["source_apk"])
        self.assertNotIn("base_apk", manifest["inputs"])
        source = ROOT / "a9_accessibility_service/src/com/lmqr/ha9_comp_service/BootReceiver.kt"
        key = f"apk_source:{source.relative_to(ROOT)}"
        self.assertEqual(manifest["inputs"][key]["sha256"], build_release.sha256(source))
        for path in ("settings.gradle.kts", "a9_accessibility_service/build.gradle.kts",
                     "a9_accessibility_service/standalone/AndroidManifest.xml",
                     "tools/android-system-api-stubs/src/main/java/android/os/SystemProperties.java"):
            self.assertIn(f"apk_source:{path}", manifest["inputs"])

    def test_experimental_phh_reduction_runs_last_and_is_recorded(self):
        for features in ([], ["--ir"], ["--xrz"], ["--ir", "--xrz"]):
            with self.subTest(features=features):
                output_root = self.work / ("phh" + "".join(features))
                commands = []
                with mock.patch.object(sys, "argv", [
                    "build-release.py", str(self.gsi), "--compatibility",
                    "--vendor-image", str(self.vendor), "--aosp-headers", str(self.headers),
                    "--experimental-phh-reduction", *features,
                    "--output-root", str(output_root),
                ]), mock.patch.object(subprocess, "run", side_effect=self.fake_build(commands)):
                    build_release.main()
                final_command = commands[-1]
                self.assertEqual(Path(final_command[1]).name, "add-phh-reduction-to-gsi.py")
                self.assertEqual(final_command[2], commands[-2][3])
                self.assertNotEqual(final_command[2], final_command[3])
                directory = next(output_root.iterdir())
                manifest = json.loads((directory / "manifest.json").read_text())
                self.assertTrue(manifest["options"]["experimental_phh_reduction"])
                self.assertIn("phh_reduction_tool", manifest["inputs"])
                self.assertEqual(list(directory.glob("*.img")), [Path(manifest["final_image"])])

    def test_experimental_phh_reduction_requires_vendor(self):
        with mock.patch.object(sys, "argv", [
            "build-release.py", str(self.gsi), "--compatibility", "--experimental-phh-reduction",
        ]), self.assertRaises(SystemExit) as result:
            build_release.main()
        self.assertEqual(result.exception.code, 2)

    def test_exactly_one_apk_source_is_required_before_creating_build_directory(self):
        for extra in ([str(self.apk)], [str(self.apk), "--source-apk"],
                      [str(self.apk), "--built-apk", str(self.apk)],
                      ["--source-apk", "--built-apk", str(self.apk)]):
            with self.subTest(extra=extra):
                output_root = self.work / "unused-builds"
                with mock.patch.object(sys, "argv", [
                    "build-release.py", str(self.gsi), "--compatibility", *extra,
                    "--output-root", str(output_root),
                ]), self.assertRaises(SystemExit) as result:
                    build_release.main()
                self.assertEqual(result.exception.code, 2)
                self.assertFalse(output_root.exists())

    def test_default_builds_source_apk(self):
        commands = []
        with mock.patch.object(sys, "argv", [
            "build-release.py", str(self.gsi), "--compatibility", "--output-root", str(self.work / "default"),
        ]), mock.patch.object(subprocess, "run", side_effect=self.fake_build(commands)):
            build_release.main()
        self.assertIn("build-source-apk.sh", [Path(command[1]).name for command in commands[:2]])

    def test_default_automates_all_stages_with_environment_inputs(self):
        commands = []
        environments = []
        build = self.fake_build(commands)
        prerequisite_barrier = threading.Barrier(3)

        def run(command, env, **kwargs):
            environments.append(env)
            if Path(command[1]).name in {
                    "build-source-apk.sh", "build-daemon.sh", "build-ir-hal.sh"}:
                prerequisite_barrier.wait(timeout=5)
            return build(command, **kwargs)

        with mock.patch.dict(build_release.os.environ, {
            "VENDOR": str(self.vendor), "AOSP_HEADERS": str(self.headers),
            "ANDROID_NDK_HOME": str(self.work / "ndk"), "SECILC": "/custom/secilc",
        }), mock.patch.object(sys, "argv", [
            "build-release.py", str(self.gsi), "--compatibility", "--ir", "--xrz",
            "--output-root", str(self.work / "all-stages"),
        ]), mock.patch.object(subprocess, "run", side_effect=run):
            build_release.main()
        self.assertEqual(len(commands), 6)
        self.assertCountEqual(
            [Path(command[1]).name for command in commands[:3]],
            ["build-source-apk.sh", "build-daemon.sh", "build-ir-hal.sh"],
        )
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
            "build-release.py", str(self.gsi), "--compatibility", "--built-apk", str(self.apk),
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
                    "build-release.py", str(self.gsi), "--compatibility", "--built-apk", str(self.apk),
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
                    "build-release.py", str(self.gsi), "--compatibility", "--built-apk", str(path),
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
            "build-release.py", str(self.gsi), "--compatibility",
            "--vendor-image", str(self.vendor), "--aosp-headers", str(self.headers),
            "--ir", "--output-root", str(output_root),
        ]), mock.patch.object(subprocess, "run", side_effect=run):
            build_release.main()
        self.assertEqual(environments[0]["AOSP_HEADERS"], str(self.headers.resolve()))

    def test_ir_requires_vendor_and_headers_before_creating_build_directory(self):
        output_root = self.work / "unused-builds"
        with mock.patch.object(sys, "argv", [
            "build-release.py", str(self.gsi), "--compatibility",
            "--ir", "--output-root", str(output_root),
        ]), self.assertRaises(SystemExit) as result:
            build_release.main()
        self.assertEqual(result.exception.code, 2)
        self.assertFalse(output_root.exists())

    def test_tested_defaults_run_all_stages(self):
        commands = []
        output = self.work / "tested"
        with mock.patch.object(build_release, "GSI_SHA256", build_release.sha256(self.gsi)), \
                mock.patch.object(build_release, "VENDOR_SHA256", build_release.sha256(self.vendor)), \
                mock.patch.object(sys, "argv", [
                    "build-release.py", str(self.gsi), "--vendor-image", str(self.vendor),
                    "--aosp-headers", str(self.headers), "--ndk", str(self.work / "ndk"),
                    "--output-root", str(output),
                ]), mock.patch.object(subprocess, "run", side_effect=self.fake_build(commands)):
            build_release.main()
        names = [Path(command[1]).name for command in commands]
        self.assertCountEqual(names[:3], ["build-daemon.sh", "build-source-apk.sh", "build-ir-hal.sh"])
        self.assertEqual(names[3:], [
            "patch-gsi.sh", "add-ir-capture-to-gsi.py", "add-xrz-compat-to-gsi.py",
            "add-phh-reduction-to-gsi.py", "add-eink-init-bridge-to-gsi.py",
            "add-eink-migration-to-gsi.py", "add-display-migration-to-gsi.py",
        ])
        for previous, current in zip(commands[3:], commands[4:]):
            self.assertEqual(previous[3], current[2])
        for command in commands[-3:]:
            self.assertEqual(command[command.index("--rebuild-gsi") + 1], str(self.gsi))
        daemon = next(command for command in commands if Path(command[1]).name == "build-daemon.sh")
        self.assertEqual(daemon[3:], ["--enforcing-migration-candidate"])
        manifest = json.loads((next(output.iterdir()) / "manifest.json").read_text())
        self.assertTrue(manifest["options"]["init_eink_bridge"])
        self.assertTrue(manifest["options"]["enforcing_eink_and_display"])
        self.assertFalse(manifest["options"]["experimental_property_only_auto_refresh"])
        self.assertEqual([stage["tool"] for stage in manifest["stages"]], names[3:])

    def test_bridge_only_build_uses_matching_daemon(self):
        commands = []
        with mock.patch.object(build_release, "GSI_SHA256", build_release.sha256(self.gsi)), \
                mock.patch.object(build_release, "VENDOR_SHA256", build_release.sha256(self.vendor)), \
                mock.patch.object(sys, "argv", [
                    "build-release.py", str(self.gsi), "--vendor-image", str(self.vendor),
                    "--aosp-headers", str(self.headers), "--ndk", str(self.work / "ndk"),
                    "--no-enforcing-migration", "--output-root", str(self.work / "bridge"),
                ]), mock.patch.object(subprocess, "run", side_effect=self.fake_build(commands)):
            build_release.main()
        daemon = next(command for command in commands if Path(command[1]).name == "build-daemon.sh")
        self.assertEqual(daemon[3:], ["--experimental-property-only-refresh", "--experimental-init-eink-bridge"])
        self.assertEqual(Path(commands[-1][1]).name, "add-eink-init-bridge-to-gsi.py")

    def test_unsupported_default_and_incompatible_switches_fail_before_build(self):
        for switches in ([], ["--no-ir"], ["--no-xrz"], ["--no-experimental-phh-reduction"],
                         ["--no-experimental-property-only-refresh"], ["--no-init-eink-bridge"],
                         ["--experimental-property-only-auto-refresh"]):
            with self.subTest(switches=switches):
                output = self.work / "must-not-exist"
                with mock.patch.object(sys, "argv", [
                    "build-release.py", str(self.gsi), "--vendor-image", str(self.vendor),
                    "--aosp-headers", str(self.headers), "--ndk", str(self.work / "ndk"),
                    "--output-root", str(output), *switches,
                ]), self.assertRaises(SystemExit) as result:
                    build_release.main()
                self.assertEqual(result.exception.code, 2)
                self.assertFalse(output.exists())

    def test_explicit_opt_outs_disable_the_requested_stages(self):
        for flag, disabled in (
            ("--no-ir", "add-ir-capture-to-gsi.py"),
            ("--no-xrz", "add-xrz-compat-to-gsi.py"),
            ("--no-experimental-phh-reduction", "add-phh-reduction-to-gsi.py"),
            ("--no-experimental-property-only-refresh", None),
        ):
            with self.subTest(flag=flag):
                commands = []
                with mock.patch.object(sys, "argv", [
                    "build-release.py", str(self.gsi), "--vendor-image", str(self.vendor),
                    "--aosp-headers", str(self.headers), "--no-enforcing-migration",
                    "--no-init-eink-bridge", flag, "--output-root", str(self.work / flag[2:]),
                ]), mock.patch.object(subprocess, "run", side_effect=self.fake_build(commands)):
                    build_release.main()
                names = [Path(command[1]).name for command in commands]
                self.assertNotIn("add-eink-init-bridge-to-gsi.py", names)
                self.assertNotIn("add-eink-migration-to-gsi.py", names)
                self.assertNotIn("add-display-migration-to-gsi.py", names)
                if disabled:
                    self.assertNotIn(disabled, names)
                else:
                    daemon = next(command for command in commands if Path(command[1]).name == "build-daemon.sh")
                    self.assertNotIn("--experimental-property-only-refresh", daemon)

    def test_unverified_vendor_rejects_tested_defaults_before_build(self):
        output = self.work / "wrong-vendor"
        with mock.patch.object(build_release, "GSI_SHA256", build_release.sha256(self.gsi)), \
                mock.patch.object(sys, "argv", [
                    "build-release.py", str(self.gsi), "--vendor-image", str(self.vendor),
                    "--aosp-headers", str(self.headers), "--ndk", str(self.work / "ndk"),
                    "--output-root", str(output),
                ]), self.assertRaises(SystemExit) as result:
            build_release.main()
        self.assertEqual(result.exception.code, 2)
        self.assertFalse(output.exists())

    def test_stage_failure_does_not_fall_back_or_write_release_manifest(self):
        commands = []
        build = self.fake_build(commands)

        def run(command, **kwargs):
            if Path(command[1]).name == "add-xrz-compat-to-gsi.py":
                raise subprocess.CalledProcessError(1, command)
            return build(command, **kwargs)

        output = self.work / "failed-stage"
        with mock.patch.object(sys, "argv", [
            "build-release.py", str(self.gsi), "--compatibility", "--xrz",
            "--vendor-image", str(self.vendor), "--output-root", str(output),
        ]), mock.patch.object(subprocess, "run", side_effect=run), self.assertRaises(SystemExit):
            build_release.main()
        directory = next(output.iterdir())
        self.assertFalse((directory / "manifest.json").exists())
        self.assertFalse((directory / "HiBreakPro-release.img").exists())

    def test_installed_daemon_mismatch_rejects_build(self):
        commands = []
        build = self.fake_build(commands)

        def run(command, **kwargs):
            result = build(command, **kwargs)
            if Path(command[1]).name == "add-eink-migration-to-gsi.py":
                output = Path(command[3])
                output.with_name(output.name + ".manifest.json").write_text(json.dumps({
                    "daemon_sha256": "wrong",
                }))
            return result

        output = self.work / "wrong-daemon"
        with mock.patch.object(build_release, "GSI_SHA256", build_release.sha256(self.gsi)), \
                mock.patch.object(build_release, "VENDOR_SHA256", build_release.sha256(self.vendor)), \
                mock.patch.object(sys, "argv", [
                    "build-release.py", str(self.gsi), "--vendor-image", str(self.vendor),
                    "--aosp-headers", str(self.headers), "--ndk", str(self.work / "ndk"),
                    "--output-root", str(output),
                ]), mock.patch.object(subprocess, "run", side_effect=run), self.assertRaisesRegex(
                    SystemExit, "does not match"):
            build_release.main()
        self.assertFalse((next(output.iterdir()) / "manifest.json").exists())
        self.assertFalse(any(Path(command[1]).name == "add-display-migration-to-gsi.py" for command in commands))


if __name__ == "__main__":
    unittest.main()
