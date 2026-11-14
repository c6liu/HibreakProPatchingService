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
SPEC = importlib.util.spec_from_file_location("build_release", ROOT / "tools/build/build-release.py")
assert SPEC is not None and SPEC.loader is not None
build_release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_release)


class ReleaseBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="release-build-test-")
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        env = mock.patch.dict(build_release.os.environ)
        env.start()
        self.addCleanup(env.stop)
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
        for name in ("consumerir.h", "hardware.h"):
            (self.headers / "hardware" / name).write_text(name)
        self.commands = []
        self.calls = []
        patcher = mock.patch.object(build_release.release_pipeline, "build", side_effect=self.fake_pipeline)
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake_run(self, command, **kwargs):
        self.commands.append((command, kwargs.get("env")))
        if command[0] == "bash":
            Path(command[2]).write_bytes(b"built")
        return subprocess.CompletedProcess(command, 0)

    def fake_pipeline(self, gsi, output, apk, daemon, vendor, hal, compiler, **options):
        self.calls.append((gsi, output, apk, daemon, vendor, hal, compiler, options))
        output.write_bytes(b"image")
        options["report"].append({"tool": "patch-gsi.py", "elapsed_seconds": 0.1})

    def run_build(self, extra, output=None):
        output = output or self.work / "build"
        with mock.patch.object(sys, "argv", [
            "build-release.py", str(self.gsi), *extra, "--output-root", str(output),
        ]), mock.patch.object(subprocess, "run", side_effect=self.fake_run):
            build_release.main()
        return json.loads((next(output.iterdir()) / "manifest.json").read_text())

    def device_inputs(self):
        return ["--vendor-image", str(self.vendor), "--aosp-headers", str(self.headers),
                "--ndk", str(self.work / "ndk")]

    def test_tested_defaults_run_unified_pipeline_and_record_options(self):
        with mock.patch.object(build_release, "GSI_SHA256", build_release.sha256(self.gsi)), \
                mock.patch.object(build_release, "VENDOR_SHA256", build_release.sha256(self.vendor)):
            manifest = self.run_build(self.device_inputs())
        self.assertEqual(len(self.calls), 1)
        gsi, output, apk, daemon, vendor, hal, compiler, flags = self.calls[0]
        self.assertEqual((gsi, vendor), (self.gsi, self.vendor))
        self.assertEqual({key: flags[key] for key in ("ir", "xrz", "reduction", "bridge", "enforcing")},
                         dict.fromkeys(("ir", "xrz", "reduction", "bridge", "enforcing"), True))
        self.assertTrue(output.name.endswith("-working.img"))
        self.assertEqual(Path(manifest["final_image"]).read_bytes(), b"image")
        self.assertEqual(manifest["inputs"]["gsi"]["sha256"], build_release.sha256(self.gsi))
        self.assertTrue(manifest["options"]["source_apk"])
        self.assertEqual(manifest["options"]["policy_jobs"], 2)
        self.assertEqual(manifest["options"]["verification_mode"], "combined")
        self.assertEqual(manifest["stages"][0]["tool"], "patch-gsi.py")
        daemon_command = next(cmd for cmd, _ in self.commands if cmd[1].endswith("build-daemon.sh"))
        self.assertIn("--enforcing-migration-candidate", daemon_command)
        self.assertEqual(len(list(Path(manifest["final_image"]).parent.glob("*.img"))), 1)

    def test_compatibility_and_explicit_features(self):
        manifest = self.run_build(["--compatibility", "--xrz", "--experimental-property-only-refresh",
                                   "--vendor-image", str(self.vendor)])
        flags = self.calls[0][-1]
        self.assertTrue(flags["xrz"])
        self.assertFalse(flags["ir"] or flags["bridge"] or flags["enforcing"])
        self.assertEqual(manifest["options"]["verification_mode"], "per-stage")
        daemon = next(cmd for cmd, _ in self.commands if cmd[1].endswith("build-daemon.sh"))
        self.assertIn("--experimental-property-only-refresh", daemon)
        self.assertTrue(manifest["options"]["experimental_property_only_refresh"])

    def test_policy_compiler_parallelism_can_be_disabled(self):
        manifest = self.run_build(["--compatibility", "--policy-jobs", "1"])
        self.assertFalse(self.calls[0][-1]["parallel_compile"])
        self.assertEqual(manifest["options"]["policy_jobs"], 1)

    def test_strict_verification_is_forwarded_and_recorded(self):
        manifest = self.run_build(["--compatibility", "--strict-verification"])
        self.assertTrue(self.calls[0][-1]["strict_verification"])
        self.assertTrue(manifest["options"]["strict_verification"])
        self.assertEqual(manifest["options"]["verification_mode"], "per-stage")

    def test_bridge_only_build_uses_matching_daemon(self):
        with mock.patch.object(build_release, "GSI_SHA256", build_release.sha256(self.gsi)), \
                mock.patch.object(build_release, "VENDOR_SHA256", build_release.sha256(self.vendor)):
            manifest = self.run_build([*self.device_inputs(), "--no-enforcing-migration"])
        daemon = next(cmd for cmd, _ in self.commands if cmd[1].endswith("build-daemon.sh"))
        self.assertEqual(daemon[3:], ["--experimental-property-only-refresh", "--experimental-init-eink-bridge"])
        self.assertTrue(manifest["options"]["init_eink_bridge"])
        self.assertFalse(manifest["options"]["enforcing_eink_and_display"])

    def test_reuses_apk_and_validates_signature(self):
        signer = self.work / "signer.jar"
        signer.write_bytes(b"signer")
        with mock.patch.dict(build_release.os.environ, {
            "APK_SIGNER_JAR": str(signer), "APK_RELEASE_CERT_SHA256": "AB:" * 31 + "AB",
        }):
            manifest = self.run_build(["--compatibility", "--built-apk", str(self.apk)])
        self.assertEqual(self.commands[0][0][0], "java")
        self.assertIn("AB" * 32, self.commands[0][0])
        self.assertEqual(manifest["inputs"]["built_apk"]["sha256"], build_release.sha256(self.apk))
        self.assertTrue(manifest["options"]["reuse_built_apk"])
        self.assertFalse(any("build-source-apk.sh" in cmd[1] for cmd, _ in self.commands))

    def test_ir_environment_is_forwarded_to_compiler(self):
        self.run_build(["--compatibility", "--ir", "--vendor-image", str(self.vendor),
                        "--aosp-headers", str(self.headers), "--ndk", str(self.work / "ndk")])
        env = next(env for cmd, env in self.commands if cmd[1].endswith("build-ir-hal.sh"))
        self.assertEqual(env["AOSP_HEADERS"], str(self.headers))
        self.assertEqual(env["ANDROID_NDK_HOME"], str(self.work / "ndk"))
        self.assertTrue(self.calls[0][-1]["ir"])

    def test_independent_inputs_still_build_concurrently(self):
        barrier = threading.Barrier(3)

        def run(command, **kwargs):
            if command[0] == "bash":
                barrier.wait(timeout=10)
            return self.fake_run(command, **kwargs)

        output = self.work / "parallel"
        with mock.patch.object(sys, "argv", [
            "build-release.py", str(self.gsi), "--compatibility", "--ir",
            "--vendor-image", str(self.vendor), "--aosp-headers", str(self.headers),
            "--output-root", str(output),
        ]), mock.patch.object(subprocess, "run", side_effect=run):
            build_release.main()
        self.assertEqual(len(self.commands), 3)

    def test_source_apk_inputs_are_recorded(self):
        manifest = self.run_build(["--compatibility", "--source-apk"])
        self.assertIn("apk_source:settings.gradle.kts", manifest["inputs"])
        self.assertIn("apk_source:eink_settings/standalone/AndroidManifest.xml",
                      manifest["inputs"])

    def test_invalid_inputs_and_unsupported_combinations_fail_before_build(self):
        cases = [
            [], ["--compatibility", "--ir"], ["--compatibility", "--experimental-phh-reduction"],
            ["--source-apk", "--built-apk", str(self.apk)],
            ["--compatibility", "--built-apk", str(self.work / "missing.apk")],
            [*self.device_inputs(), "--no-ir"], [*self.device_inputs(), "--no-xrz"],
            [*self.device_inputs(), "--no-experimental-phh-reduction"],
            [*self.device_inputs(), "--no-experimental-property-only-refresh"],
            [*self.device_inputs(), "--no-init-eink-bridge"],
            [*self.device_inputs(), "--experimental-property-only-auto-refresh"],
            self.device_inputs(), ["--compatibility", "--policy-jobs", "3"],
        ]
        for index, switches in enumerate(cases):
            with self.subTest(switches=switches):
                output = self.work / f"invalid-{index}"
                with mock.patch.object(sys, "argv", ["build-release.py", str(self.gsi),
                                                    *switches, "--output-root", str(output)]), \
                        self.assertRaises(SystemExit) as result:
                    build_release.main()
                self.assertEqual(result.exception.code, 2)
                self.assertFalse(output.exists())

    def test_each_opt_out_is_forwarded(self):
        for flag, option in (("--no-ir", "ir"), ("--no-xrz", "xrz"),
                             ("--no-experimental-phh-reduction", "reduction")):
            with self.subTest(flag=flag):
                self.run_build([*self.device_inputs(), "--no-enforcing-migration",
                                "--no-init-eink-bridge", flag], self.work / option)
                self.assertFalse(self.calls[-1][-1][option])
        self.run_build([*self.device_inputs(), "--no-enforcing-migration",
                        "--no-init-eink-bridge", "--no-experimental-property-only-refresh"],
                       self.work / "no-refresh")
        daemon = [cmd for cmd, _ in self.commands if cmd[1].endswith("build-daemon.sh")][-1]
        self.assertNotIn("--experimental-property-only-refresh", daemon)

    def test_failed_pipeline_does_not_publish_image_or_manifest(self):
        with mock.patch.object(build_release.release_pipeline, "build", side_effect=ValueError("failed")), \
                self.assertRaisesRegex(SystemExit, "failed"):
            self.run_build(["--compatibility"], self.work / "failure")
        directory = next((self.work / "failure").iterdir())
        self.assertFalse((directory / "manifest.json").exists())
        self.assertFalse((directory / "HiBreakPro-release.img").exists())
        self.assertFalse(any(directory.glob(".release-stages-*")))

    def test_failed_signature_verification_stops_before_pipeline(self):
        signer = self.work / "signer.jar"
        signer.write_bytes(b"signer")
        with mock.patch.dict(build_release.os.environ, {"APK_SIGNER_JAR": str(signer)}), \
                mock.patch.object(subprocess, "run", side_effect=subprocess.CalledProcessError(1, ["java"])), \
                mock.patch.object(sys, "argv", ["build-release.py", str(self.gsi), "--compatibility",
                                               "--built-apk", str(self.apk), "--output-root", str(self.work / "failed")]), \
                self.assertRaises(SystemExit):
            build_release.main()
        self.assertFalse(self.calls)


if __name__ == "__main__":
    unittest.main()
