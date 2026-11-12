import importlib.util
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

from tools.hibreak import elf, image, policy


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("ir_overlay", ROOT / "tools/image/add-ir-capture-to-gsi.py")
overlay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(overlay)


class IrOverlayTests(unittest.TestCase):
    def build_hal_fixture(self, work, symbol=True):
        compiler = shutil.which("cc")
        if not compiler or not shutil.which("readelf"):
            self.skipTest("Missing C compiler or readelf")
        source = work / "hal.c"
        source.write_text("char " + ("HMI" if symbol else "unrelated") + "[248] = {1};\nvoid code(void) {}\n")
        module = work / ("hal.so" if symbol else "unrelated.so")
        subprocess.run([compiler, "-shared", "-fPIC", "-nostdlib", source, "-o", module], check=True)
        # Host fixtures exercise ELF validation, not execution; production is built with the NDK.
        data = bytearray(module.read_bytes())
        data[18:20] = b"\xb7\x00"
        module.write_bytes(data)
        return module

    def test_hal_rejects_truncated_headers_segments_and_missing_export(self):
        with tempfile.TemporaryDirectory(prefix="ir-hal-validation-") as directory:
            work = Path(directory)
            module = self.build_hal_fixture(work)
            overlay.validate_hal_module(module)
            good = module.read_bytes()
            for content in (good[:64], good[:-256]):
                module.write_bytes(content)
                with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                    overlay.validate_hal_module(module)
            module.write_bytes(good)
            data = bytearray(good)
            data[32:40] = (len(good) + 1).to_bytes(8, "little")
            module.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "program headers"):
                overlay.validate_hal_module(module)
            with self.assertRaisesRegex(ValueError, "HMI"):
                overlay.validate_hal_module(self.build_hal_fixture(work, symbol=False))
            module.write_bytes(good)
            phoff = struct.unpack_from("<Q", good, 32)[0]
            phnum = struct.unpack_from("<H", good, 56)[0]
            for kind, message in ((1, "LOAD"), (2, "DYNAMIC")):
                data = bytearray(good)
                for index in range(phnum):
                    offset = phoff + index * 56
                    if struct.unpack_from("<I", data, offset)[0] == kind:
                        struct.pack_into("<I", data, offset, 0)
                module.write_bytes(data)
                with self.assertRaisesRegex(ValueError, message):
                    overlay.validate_hal_module(module)
            data = bytearray(good)
            for index in range(phnum):
                offset = phoff + index * 56
                if struct.unpack_from("<I", data, offset)[0] == 2:
                    old_offset = struct.unpack_from("<Q", data, offset + 8)[0]
                    struct.pack_into("<Q", data, offset + 8, old_offset - 16)
            module.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "dynamic table"):
                overlay.validate_hal_module(module)
            module.write_bytes(good)
            symbols = subprocess.CompletedProcess([], 0, b"1: 0000000000001000 248 OBJECT GLOBAL DEFAULT 8 HMI\n", b"")
            for details, message in ((b"(NEEDED) Shared library: [libunavailable.so]\n", "dependencies"),
                                     (b"(TEXTREL)\n", "text relocations")):
                with mock.patch.object(elf.subprocess, "run", side_effect=[
                    symbols, subprocess.CompletedProcess([], 0, details, b""),
                ]):
                    with self.assertRaisesRegex(ValueError, message):
                        overlay.validate_hal_module(module)

    def test_release_policy_excludes_diagnostic_domains_and_contexts(self):
        def extract(_image, path, destination):
            destination.write_text("31.0\n" if path.endswith("plat_sepolicy_vers.txt") else "# fixture\n")
            return destination

        with tempfile.TemporaryDirectory(prefix="ir-release-policy-") as directory, \
                mock.patch.object(image, "extract", side_effect=extract), \
                mock.patch.object(image, "image_exists", side_effect=lambda _image, path: not path.startswith("/odm/")), \
                mock.patch.object(overlay.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"", b"")):
            platform, contexts, _ = overlay.prepare_policy(
                Path("base"), Path("vendor"), Path(directory), "secilc", hal=True,
            )
            for excluded in ("hibreak_ir_capture", "hibreak_ir_remote", "hibreak_ir_request_prop"):
                self.assertNotIn(excluded, platform.read_text())
                self.assertNotIn(excluded, contexts.read_text())
            self.assertIn("hibreak_ir_hal_file", platform.read_text())
            self.assertIn("consumerir", contexts.read_text())

    def test_existing_ir_policy_can_be_read_but_not_overlaid_again(self):
        def extract(_image, path, destination):
            content = "31.0\n" if path.endswith("plat_sepolicy_vers.txt") else "# fixture\n"
            if path.endswith("plat_sepolicy.cil"):
                content = "(type hibreak_ir_hal_file)\n"
            destination.write_text(content)
            return destination

        with tempfile.TemporaryDirectory(prefix="ir-existing-policy-") as directory, \
                mock.patch.object(image, "extract", side_effect=extract), \
                mock.patch.object(image, "image_exists", side_effect=lambda _image, path: not path.startswith("/odm/")), \
                mock.patch.object(overlay.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"", b"")):
            args = (Path("base"), Path("vendor"), Path(directory), "secilc")
            with self.assertRaisesRegex(ValueError, "IR policy already present"):
                overlay.prepare_policy(*args)
            platform, _, _ = overlay.prepare_policy(*args, allow_existing_ir=True)
            self.assertIn("(type hibreak_ir_hal_file)", platform.read_text())
            with self.assertRaisesRegex(ValueError, "Cannot add another IR overlay"):
                overlay.prepare_policy(*args, hal=True, allow_existing_ir=True)

    def test_unchanged_policy_is_not_compiled_twice(self):
        def extract(_image, path, destination):
            destination.write_text("31.0\n" if path.endswith("plat_sepolicy_vers.txt") else "# fixture\n")
            return destination

        with tempfile.TemporaryDirectory(prefix="ir-policy-reuse-") as directory, \
                mock.patch.object(image, "extract", side_effect=extract), \
                mock.patch.object(image, "image_exists", side_effect=lambda _image, path: not path.startswith("/odm/")), \
                mock.patch.object(overlay.subprocess, "run",
                                  return_value=subprocess.CompletedProcess([], 0, b"", b"")) as compiler:
            diagnostics = []
            overlay.prepare_policy(Path("base"), Path("vendor"), Path(directory), "secilc",
                                   allow_existing_ir=True, diagnostics_out=diagnostics)
            self.assertEqual(compiler.call_count, 1)
            self.assertEqual(diagnostics, [set()])

    def test_extract_policy_inputs_does_not_compile_or_modify_policy(self):
        def extract(_image, path, destination):
            destination.write_text("31.0\n" if path.endswith("plat_sepolicy_vers.txt") else "# fixture\n")
            return destination

        with tempfile.TemporaryDirectory(prefix="ir-policy-inputs-") as directory, \
                mock.patch.object(image, "extract", side_effect=extract), \
                mock.patch.object(image, "image_exists", side_effect=lambda _image, path: not path.startswith("/odm/")), \
                mock.patch.object(policy.subprocess, "run") as compiler:
            platform, inputs = policy.extract_policy_inputs(Path("base"), Path("vendor"), Path(directory))
            self.assertEqual([path.name for path in inputs], [
                "plat.cil", "plat-mapping.cil", "plat-mapping.compat.cil",
                "ext.cil", "ext-mapping.cil", "ext-mapping.compat.cil",
                "product.cil", "product-mapping.cil", "product-mapping.compat.cil",
                "plat_pub_versioned.cil", "vendor_sepolicy.cil",
            ])
            self.assertEqual(platform.read_text(), "# fixture\n")
            compiler.assert_not_called()

    def test_parallel_policy_compile_uses_independent_outputs(self):
        baseline = b"neverallow check failed at plat.cil:1\n  (neverallow a b (file (read)))\n"
        barrier = threading.Barrier(2)
        paths = []

        def extract(_image, path, destination):
            destination.write_text("31.0\n" if path.endswith("plat_sepolicy_vers.txt") else "# fixture\n")
            return destination

        def checked(command, **_kwargs):
            paths.append(command[command.index("-o") + 1])
            barrier.wait(timeout=10)
            return subprocess.CompletedProcess(command, 255, b"", baseline)

        def runtime(*command):
            paths.append(command[command.index("-o") + 1])
            self.assertEqual(command[-1], "-N")
            Path(command[command.index("-o") + 1]).write_bytes(b"compiled")
            Path(command[command.index("-f") + 1]).write_bytes(b"contexts")
            barrier.wait(timeout=10)
            return subprocess.CompletedProcess(command, 0)

        with tempfile.TemporaryDirectory(prefix="ir-policy-parallel-") as directory, \
                mock.patch.object(image, "extract", side_effect=extract), \
                mock.patch.object(image, "image_exists", side_effect=lambda _image, path: not path.startswith("/odm/")), \
                mock.patch.object(policy.subprocess, "run", side_effect=checked), \
                mock.patch.object(image, "run", side_effect=runtime):
            diagnostics = []
            policy.prepare_ir_policy(Path("base"), Path("vendor"), Path(directory), "secilc",
                                     allow_existing_ir=True, parallel_compile=True,
                                     diagnostics_out=diagnostics)
            self.assertEqual(diagnostics, [{baseline.decode()}])
            self.assertEqual((Path(directory) / "validated.policy").read_bytes(), b"compiled")
            self.assertEqual((Path(directory) / "validated.contexts").read_bytes(), b"contexts")
            self.assertEqual(len(set(paths)), 2)

    def test_compile_pair_runs_both_checks_concurrently(self):
        barrier = threading.Barrier(2)
        seen = []
        failure = b"neverallow check failed at plat.cil:1\n  (neverallow a b (file (read)))\n"
        command = ["secilc", "input.cil", "-o", "policy", "-f", "contexts"]

        def checked(args, **_kwargs):
            seen.append(args)
            barrier.wait(timeout=10)
            return subprocess.CompletedProcess(args, 255, b"", failure)

        def runtime(*args):
            seen.append(args)
            barrier.wait(timeout=10)
            return subprocess.CompletedProcess(args, 0)

        with mock.patch.object(policy.subprocess, "run", side_effect=checked), \
                mock.patch.object(image, "run", side_effect=runtime):
            self.assertEqual(policy.compile_pair(command), {failure.decode()})
        checked_args = next(args for args in seen if args[-1] != "-N")
        runtime_args = next(args for args in seen if args[-1] == "-N")
        self.assertEqual(checked_args[checked_args.index("-o") + 1], "policy.checked")
        self.assertEqual(checked_args[checked_args.index("-f") + 1], "contexts.checked")
        self.assertEqual(runtime_args[runtime_args.index("-o") + 1], "policy")

    def test_release_requires_explicit_feature_and_diagnostic_opt_in(self):
        for options in ([], ["--remote-apk", "remote.apk"]):
            with self.subTest(options=options), mock.patch.object(
                sys, "argv", ["overlay", "base.img", "output.img", "--vendor-image", "vendor.img", *options],
            ):
                with self.assertRaises(SystemExit) as result:
                    overlay.main()
                self.assertEqual(result.exception.code, 2)

    def test_compiler_errors_are_not_silently_ignored(self):
        with self.assertRaisesRegex(ValueError, "Policy compilation failed"):
            overlay.neverallow_failures(subprocess.CompletedProcess([], 1, b"", b"Unknown type ctrl_device"))
        self.assertEqual(overlay.neverallow_failures(subprocess.CompletedProcess([], 0, b"", b"")), set())
        failure = "neverallow check failed at plat.cil:1\n  (neverallow a b (file (read)))\n"
        self.assertEqual(
            overlay.neverallow_failures(subprocess.CompletedProcess([], 1, b"", (failure + "\nFailed to generate binary").encode())),
            {failure},
        )

    def test_neverallow_and_neverallowx_diagnostics_are_separate(self):
        ordinary = "neverallow check failed at plat.cil:1\n  (neverallow a b (file (read)))\n"
        extended = "neverallowx check failed at plat.cil:2\n  (neverallowx a b (ioctl chr_file (0x5412)))\n"
        for failures in ([extended], [ordinary, extended], [extended, ordinary],
                         [ordinary, extended, ordinary]):
            with self.subTest(failures=failures):
                result = subprocess.CompletedProcess(
                    [], 255, b"",
                    ("\n".join(failures) + "\nFailed to generate binary\n").encode(),
                )
                self.assertEqual(policy.neverallow_failures(result), set(failures))
        for ending in ("", "\n", "\n\nFailed to generate binary\n"):
            result = subprocess.CompletedProcess([], 255, b"", (extended.rstrip("\n") + ending).encode())
            self.assertEqual(policy.neverallow_failures(result), {extended})

    def test_policy_rejects_new_extended_permission_conflicts(self):
        ordinary = b"neverallow check failed at plat.cil:1\n  (neverallow a b (file (read)))\n"
        extended = b"neverallowx check failed at plat.cil:2\n  (neverallowx a b (ioctl chr_file (0x5412)))\n"

        def extract(_image, path, destination):
            destination.write_text("31.0\n" if path.endswith("plat_sepolicy_vers.txt") else "# fixture\n")
            return destination

        for baseline, modified in ((b"", extended), (ordinary, ordinary + b"\n" + extended),
                                   (extended, extended + b"\n" + ordinary)):
            with self.subTest(baseline=baseline), tempfile.TemporaryDirectory() as directory, \
                    mock.patch.object(image, "extract", side_effect=extract), \
                    mock.patch.object(image, "image_exists", side_effect=lambda _image, path: not path.startswith("/odm/")), \
                    mock.patch.object(policy.subprocess, "run", side_effect=[
                        subprocess.CompletedProcess([], 255 if baseline else 0, b"", baseline),
                        subprocess.CompletedProcess([], 255, b"", modified),
                    ]), mock.patch.object(image, "run") as runtime_compile:
                with self.assertRaisesRegex(ValueError, "IR overlay adds neverallow violations"):
                    policy.prepare_ir_policy(Path("base"), Path("vendor"), Path(directory), "secilc",
                                             diagnostics=True)
                runtime_compile.assert_not_called()

    def test_existing_extended_permission_conflicts_use_runtime_compile(self):
        extended = b"neverallowx check failed at plat.cil:2\n  (neverallowx a b (ioctl chr_file (0x5412)))\n"

        def extract(_image, path, destination):
            destination.write_text("31.0\n" if path.endswith("plat_sepolicy_vers.txt") else "# fixture\n")
            return destination

        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(image, "extract", side_effect=extract), \
                mock.patch.object(image, "image_exists", side_effect=lambda _image, path: not path.startswith("/odm/")), \
                mock.patch.object(policy.subprocess, "run", return_value=subprocess.CompletedProcess([], 255, b"", extended)), \
                mock.patch.object(image, "run") as runtime_compile, \
                mock.patch("builtins.print") as output:
            diagnostics = []
            policy.prepare_ir_policy(Path("base"), Path("vendor"), Path(directory), "secilc",
                                     diagnostics_out=diagnostics)
            self.assertEqual(diagnostics, [{extended.decode()}])
            runtime_compile.assert_called_once()
            self.assertEqual(runtime_compile.call_args.args[-1], "-N")
            self.assertIn("1 existing neverallow/neverallowx conflicts", output.call_args_list[0].args[0])

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
            with mock.patch.object(image, "extract", side_effect=extract), \
                    mock.patch.object(image, "image_exists", side_effect=lambda _image, path: not path.startswith("/odm/")):
                with mock.patch.object(overlay.subprocess, "run", side_effect=[
                    result(baseline), result(added + baseline),
                ]) as compile_policy:
                    with self.assertRaisesRegex(ValueError, "IR overlay adds neverallow violations"):
                        overlay.prepare_policy(Path("gsi"), Path("vendor"), Path(directory), "secilc",
                                               diagnostics=True)
                    self.assertEqual(compile_policy.call_count, 2)
                with mock.patch.object(overlay.subprocess, "run", side_effect=[
                    result(baseline), result(baseline), subprocess.CompletedProcess([], 0, b"", b""),
                ]) as compile_policy:
                    overlay.prepare_policy(Path("gsi"), Path("vendor"), Path(directory), "secilc",
                                           diagnostics=True)
                    self.assertEqual(compile_policy.call_count, 3)
                    self.assertIn("-N", compile_policy.call_args.args[0])

    def test_ext4_overlay_roundtrip_and_refusal_to_overwrite(self):
        for remote, hal, diagnostics, api in (
            (False, False, True, False), (True, False, True, False),
            (False, True, True, False), (True, True, True, True),
            (False, True, False, False), (False, True, False, True),
        ):
            with self.subTest(remote=remote, hal=hal, diagnostics=diagnostics, api=api):
                self._overlay_roundtrip(remote, hal, diagnostics, api)

    def _overlay_roundtrip(self, remote, hal, diagnostics, api):
        for tool in ("debugfs", "mke2fs", "e2fsck", "resize2fs", "dumpe2fs"):
            if not shutil.which(tool):
                self.skipTest(f"Missing {tool}")
        with tempfile.TemporaryDirectory(prefix="ir-overlay-test-") as directory:
            work = Path(directory)
            source, output, binary = (work / name for name in ("base.img", "output.img", "hxd-learn"))
            with source.open("wb") as stream:
                stream.truncate(32 * 1024 * 1024)
            subprocess.run(["mke2fs", "-q", "-t", "ext4", "-F", source], check=True)
            for path in ("system", "system/etc", "system/etc/selinux", "system/etc/init", "system/bin",
                         "system/priv-app", "system/app", "system/lib64", "lib64", "lib64/hw", "etc", "etc/init"):
                overlay.run("debugfs", "-w", "-R", f"mkdir {path}", str(source))
            context_source = work / "context-source"
            context_source.write_text("# existing context\n")
            for name in ("plat_seapp_contexts", "plat_property_contexts"):
                overlay.install(source, context_source, f"system/etc/selinux/{name}",
                                "0100644", "u:object_r:system_file:s0", work)
            original = source.read_bytes()
            elf = bytearray(120)
            elf[:7] = b"\x7fELF\x02\x01\x01"
            elf[18:20] = b"\xb7\x00"
            elf[32:40] = (64).to_bytes(8, "little")
            elf[54:56] = (56).to_bytes(2, "little")
            elf[56:58] = (1).to_bytes(2, "little")
            elf[64:68] = (1).to_bytes(4, "little")
            binary.write_bytes(elf)
            module = self.build_hal_fixture(work)
            vendor_rc = work / "vendor.rc"
            vendor_rc.write_text("service vendor.ir-hal-1-0 /vendor/bin/hw/android.hardware.ir@1.0-service\n    class hal\n")
            overlay.install(source, module, "lib64/hw/consumerir.common.so",
                            "0100644", "u:object_r:vendor_file:s0", work)
            overlay.install(source, vendor_rc, "etc/init/android.hardware.ir@1.0-service.rc",
                            "0100644", "u:object_r:vendor_file:s0", work)
            original = source.read_bytes()

            def policy(_source, _vendor, temporary, _compiler, **kwargs):
                self.assertEqual(kwargs.get("remote", False), remote)
                self.assertEqual(kwargs.get("hal", False), hal)
                self.assertEqual(kwargs.get("diagnostics", False), diagnostics)
                cil, contexts = temporary / "plat.cil", temporary / "contexts"
                cil.write_text("(type fixture)\n")
                contexts.write_text((ROOT / "tools/ir/hibreak-ir-file-contexts").read_text())
                return cil, contexts, [cil]

            argv = ["overlay", str(source), str(output),
                    "--vendor-image", str(source), "--secilc", "true"]
            if diagnostics:
                argv.extend(["--diagnostics-binary", str(binary)])
            if api:
                api_apk = work / "api.apk"
                api_apk.write_bytes(b"test API APK")
                argv.extend(["--api-test-apk", str(api_apk)])
            if remote:
                apk = work / "remote.apk"
                apk.write_bytes(b"test APK")
                argv.extend(["--remote-apk", str(apk)])
            if hal:
                argv.extend(["--hal-module", str(module)])
            with mock.patch.object(sys, "argv", argv), mock.patch.object(overlay, "prepare_policy", side_effect=policy):
                overlay.main()
                self.assertEqual(source.read_bytes(), original)
                if diagnostics:
                    self.assertEqual(
                        overlay.run("debugfs", "-R", "cat system/etc/init/hibreak-ir-capture.rc", str(output)).stdout,
                        (ROOT / "tools/ir/hibreak-ir-capture.rc").read_bytes(),
                    )
                    stat = overlay.run("debugfs", "-R", "stat system/bin/hxd-learn", str(output)).stdout.decode()
                    self.assertIn("Mode:  0755", stat)
                    self.assertIn("u:object_r:hibreak_ir_capture_exec:s0", stat)
                else:
                    self.assertFalse(overlay.image_exists(output, "system/bin/hxd-learn"))
                    self.assertFalse(overlay.image_exists(output, "system/etc/init/hibreak-ir-capture.rc"))
                    self.assertFalse(overlay.image_exists(output, "system/etc/init/hibreak-ir-remote.rc"))
                self.assertEqual(overlay.image_exists(output, "system/app/HiBreakIrApiTest"), api)
                if api:
                    self.assertEqual(
                        overlay.run("debugfs", "-R", "cat system/app/HiBreakIrApiTest/HiBreakIrApiTest.apk", str(output)).stdout,
                        b"test API APK",
                    )
                if remote:
                    apk_path = "system/priv-app/HiBreakIrRemote/HiBreakIrRemote.apk"
                    self.assertEqual(overlay.run("debugfs", "-R", f"cat {apk_path}", str(output)).stdout, b"test APK")
                    for name, suffix in (("plat_seapp_contexts", "seapp-contexts"),
                                         ("plat_property_contexts", "property-contexts")):
                        self.assertEqual(
                            overlay.run("debugfs", "-R", f"cat system/etc/selinux/{name}", str(output)).stdout,
                            b"# existing context\n\n" + (ROOT / f"tools/ir/hibreak-ir-remote-{suffix}").read_bytes(),
                        )
                    self.assertEqual(
                        overlay.run("debugfs", "-R", "cat system/etc/init/hibreak-ir-remote.rc", str(output)).stdout,
                        (ROOT / "tools/ir/hibreak-ir-remote.rc").read_bytes(),
                    )
                else:
                    self.assertFalse(overlay.image_exists(output, "system/priv-app/HiBreakIrRemote"))
                if hal:
                    self.assertEqual(
                        overlay.run("debugfs", "-R", "cat system/lib64/consumerir.hxd.so", str(output)).stdout,
                        module.read_bytes(),
                    )
                    self.assertIn("u:object_r:hibreak_ir_hal_file:s0", overlay.run(
                        "debugfs", "-R", "stat system/lib64/consumerir.hxd.so", str(output)).stdout.decode())
                    self.assertEqual(
                        overlay.run("debugfs", "-R", "cat system/etc/init/hibreak-ir-hal.rc", str(output)).stdout,
                        (ROOT / "tools/ir/hibreak-ir-hal.rc").read_bytes(),
                    )
                else:
                    self.assertFalse(overlay.image_exists(output, "system/lib64/consumerir.hxd.so"))
                with self.assertRaises(SystemExit):
                    overlay.main()
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
