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
build_release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_release)


class ReleaseBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="release-build-test-")
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
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
            if command[0] == "bash" and command[1].endswith("build-apk.sh"):
                output = Path(command[3])
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
            "build-release.py", str(self.gsi), str(self.apk),
            "--vendor-image", str(self.vendor),
            "--aosp-headers", str(self.headers),
            "--ir", "--xrz", "--output-root", str(output_root),
        ]), mock.patch.object(subprocess, "run", side_effect=self.fake_build(commands)):
            build_release.main()

        self.assertEqual(len(commands), 6)
        self.assertTrue(commands[0][1].endswith("build-apk.sh"))
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
        self.assertEqual(manifest["options"], {"ir": True, "xrz_v2": True, "release": True})
        self.assertEqual(Path(manifest["final_image"]).name, "HiBreakPro-xrz-v2-test.img")
        self.assertEqual(manifest["inputs"]["gsi"]["sha256"], build_release.sha256(self.gsi))
        self.assertIn("HiBreakPro-release-base.img", manifest["outputs"])
        self.assertIn("HiBreakPro-release-ir.img", manifest["outputs"])
        self.assertIn("HiBreakPro-xrz-v2-test.img", manifest["outputs"])
        self.assertEqual(commands[4][1], str(ROOT / "tools/add-ir-capture-to-gsi.py"))

    def test_ir_header_path_is_passed_to_build_command_environment(self):
        output_root = self.work / "builds"
        environments = []
        commands = []
        build = self.fake_build(commands)

        def run(command, env, **_kwargs):
            environments.append(env)
            return build(command)

        with mock.patch.object(sys, "argv", [
            "build-release.py", str(self.gsi), str(self.apk),
            "--vendor-image", str(self.vendor), "--aosp-headers", str(self.headers),
            "--ir", "--output-root", str(output_root),
        ]), mock.patch.object(subprocess, "run", side_effect=run):
            build_release.main()
        self.assertEqual(environments[0]["AOSP_HEADERS"], str(self.headers.resolve()))

    def test_ir_requires_vendor_and_headers_before_creating_build_directory(self):
        output_root = self.work / "unused-builds"
        with mock.patch.object(sys, "argv", [
            "build-release.py", str(self.gsi), str(self.apk),
            "--ir", "--output-root", str(output_root),
        ]), self.assertRaises(SystemExit) as result:
            build_release.main()
        self.assertEqual(result.exception.code, 2)
        self.assertFalse(output_root.exists())


if __name__ == "__main__":
    unittest.main()
