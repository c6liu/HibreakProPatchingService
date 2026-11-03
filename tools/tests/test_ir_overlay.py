import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("ir_overlay", ROOT / "tools/add-ir-capture-to-gsi.py")
overlay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(overlay)


class IrOverlayTests(unittest.TestCase):
    def test_compiler_errors_are_not_silently_ignored(self):
        with self.assertRaisesRegex(ValueError, "Policy compilation failed"):
            overlay.neverallow_failures(subprocess.CompletedProcess([], 1, b"", b"Unknown type ctrl_device"))
        self.assertEqual(overlay.neverallow_failures(subprocess.CompletedProcess([], 0, b"", b"")), set())
        failure = "neverallow check failed at plat.cil:1\n  (neverallow a b (file (read)))\n"
        self.assertEqual(
            overlay.neverallow_failures(subprocess.CompletedProcess([], 1, b"", (failure + "\nFailed to generate binary").encode())),
            {failure},
        )

    def test_service_is_explicit_unprivileged_and_fixed(self):
        rc = (ROOT / "tools/ir/hibreak-ir-capture.rc").read_text()
        self.assertIn("user shell\n", rc)
        self.assertIn("    disabled\n    oneshot\n    timeout_period 35", rc)
        self.assertIn("on property:debug.hibreak.ir_capture=1", rc)
        self.assertIn("on property:debug.hibreak.ir_cancel=1", rc)
        self.assertEqual(rc.count("    start hibreak_ir_capture"), 1)
        self.assertNotIn("on boot", rc)
        self.assertNotIn("sys.boot_completed", rc)
        self.assertIn("--service ${debug.hibreak.ir_mode:-extended}", rc)
        self.assertNotIn("permissive", (ROOT / "tools/ir/hibreak-ir-capture.cil").read_text())

    def test_existing_neverallow_conflicts_allowed_but_new_ones_rejected(self):
        baseline = b"neverallow check failed at vendor.cil:1\n  existing conflict\n\nFailed to generate binary\n"
        added = b"neverallow check failed at plat.cil:2\n  new IR conflict\n\n"

        def result(diagnostics):
            return subprocess.CompletedProcess([], 1, b"", diagnostics)

        def extract(_image, path, destination):
            destination.write_text("31.0\n" if path.endswith("plat_sepolicy_vers.txt") else "(type fixture)\n")
            return destination

        with tempfile.TemporaryDirectory(prefix="ir-policy-test-") as directory:
            with mock.patch.object(overlay, "extract", side_effect=extract), \
                    mock.patch.object(overlay, "image_exists", side_effect=lambda _image, path: not path.startswith("/odm/")):
                with mock.patch.object(overlay.subprocess, "run", side_effect=[
                    result(baseline), result(added + baseline),
                ]) as compile_policy:
                    with self.assertRaisesRegex(ValueError, "IR overlay adds neverallow violations"):
                        overlay.prepare_policy(Path("gsi"), Path("vendor"), Path(directory), "secilc")
                    self.assertEqual(compile_policy.call_count, 2)
                with mock.patch.object(overlay.subprocess, "run", side_effect=[
                    result(baseline), result(baseline), subprocess.CompletedProcess([], 0, b"", b""),
                ]) as compile_policy:
                    overlay.prepare_policy(Path("gsi"), Path("vendor"), Path(directory), "secilc")
                    self.assertEqual(compile_policy.call_count, 3)
                    self.assertIn("-N", compile_policy.call_args.args[0])

    def test_ext4_overlay_roundtrip_and_refusal_to_overwrite(self):
        for tool in ("debugfs", "mke2fs", "e2fsck", "resize2fs", "dumpe2fs"):
            if not shutil.which(tool):
                self.skipTest(f"Missing {tool}")
        with tempfile.TemporaryDirectory(prefix="ir-overlay-test-") as directory:
            work = Path(directory)
            source, output, binary = (work / name for name in ("base.img", "output.img", "hxd-learn"))
            with source.open("wb") as stream:
                stream.truncate(32 * 1024 * 1024)
            subprocess.run(["mke2fs", "-q", "-t", "ext4", "-F", source], check=True)
            for path in ("system", "system/etc", "system/etc/selinux", "system/etc/init", "system/bin"):
                overlay.run("debugfs", "-w", "-R", f"mkdir {path}", str(source))
            original = source.read_bytes()
            elf = bytearray(120)
            elf[:6] = b"\x7fELF\x02\x01"
            elf[18:20] = b"\xb7\x00"
            elf[32:40] = (64).to_bytes(8, "little")
            elf[54:56] = (56).to_bytes(2, "little")
            elf[56:58] = (1).to_bytes(2, "little")
            elf[64:68] = (1).to_bytes(4, "little")
            binary.write_bytes(elf)

            def policy(_source, _vendor, temporary, _compiler):
                cil, contexts = temporary / "plat.cil", temporary / "contexts"
                cil.write_text("(type fixture)\n")
                contexts.write_text((ROOT / "tools/ir/hibreak-ir-file-contexts").read_text())
                return cil, contexts, [cil]

            argv = ["overlay", str(source), str(output), str(binary),
                    "--vendor-image", str(source), "--secilc", "true"]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(overlay, "prepare_policy", side_effect=policy):
                overlay.main()
                self.assertEqual(source.read_bytes(), original)
                self.assertEqual(
                    overlay.run("debugfs", "-R", "cat system/etc/init/hibreak-ir-capture.rc", str(output)).stdout,
                    (ROOT / "tools/ir/hibreak-ir-capture.rc").read_bytes(),
                )
                stat = overlay.run("debugfs", "-R", "stat system/bin/hxd-learn", str(output)).stdout.decode()
                self.assertIn("Mode:  0755", stat)
                self.assertIn("u:object_r:hibreak_ir_capture_exec:s0", stat)
                with self.assertRaises(SystemExit):
                    overlay.main()
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
