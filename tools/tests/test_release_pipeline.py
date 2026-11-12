import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tools.hibreak import release_pipeline as pipeline


class ReleasePipelineTests(unittest.TestCase):
    def test_all_stages_use_one_image_and_verify_each_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output, vendor, apk, daemon, hal = [root / n for n in
                                                        ("source", "working", "vendor", "apk", "daemon", "hal")]
            for path in (source, vendor, apk, daemon, hal):
                path.write_bytes(b"fixture")
            prepared = root / "prepared"
            prepared.write_bytes(b"policy")
            calls = []

            def initial(gsi, target, _apk, _daemon, key, release, keep_root, finalize):
                self.assertEqual((gsi, target, key, release, keep_root, finalize),
                                 (source, output, None, True, False, False))
                target.write_bytes(b"working")

            patch = SimpleNamespace(patch_image=initial, validate_paths=lambda paths: None)
            ir = SimpleNamespace(prepare_policy=lambda *args, **kwargs: (prepared, prepared, [prepared]))
            xrz = SimpleNamespace(prepare_compatibility=lambda *args, **kwargs: [prepared] * 4,
                                  MAPPING="mapping", PLAT_CONTEXTS="contexts")
            phh = SimpleNamespace(prepare_reduction=lambda *args, **kwargs: [prepared] * 2, EXT_POLICY="ext")
            bridge = SimpleNamespace(prepare_bridge=lambda *args, **kwargs: [prepared] * 3,
                                     PLAT_CONTEXTS="properties", DISPLAY=root)
            migration = SimpleNamespace(validate=lambda *args, **kwargs: (prepared, prepared, [prepared]))

            def make_contexts(path):
                path.write_text("contexts")

            eink = SimpleNamespace(migration=migration, prepare_file_contexts=make_contexts,
                                   policy_digest=lambda *args: prepared, EXEC_PATH="exec",
                                   INIT_PATH="init", EXEC_CONTEXT="exec-label",
                                   PROPERTY_CONTEXTS="properties", FILE_CONTEXTS="contexts", DISPLAY=root)
            display = SimpleNamespace(prepare=lambda *args, **kwargs: [prepared] * 5,
                                      PROPERTY_CONTEXTS="properties", INIT_PATH="display-init", AOD_PATH="aod")
            modules = {"patch-gsi.py": patch, "add-ir-capture-to-gsi.py": ir,
                       "add-xrz-compat-to-gsi.py": xrz, "add-phh-reduction-to-gsi.py": phh}

            def extract(_img, path, destination):
                destination.write_bytes(b"\x7fELF\x02\x01" if path.endswith(".so") else b"class hal")
                return destination

            with mock.patch.object(pipeline, "load", side_effect=lambda _name, file: modules[file]), \
                    mock.patch.object(pipeline.shutil, "which", return_value="/tool"), \
                    mock.patch.object(pipeline, "eink_bridge", bridge), \
                    mock.patch.object(pipeline, "eink_migration", eink), \
                    mock.patch.object(pipeline, "display_migration", display), \
                    mock.patch.object(pipeline, "validate_hal_module"), \
                    mock.patch.object(pipeline, "validate_rebuild", side_effect=lambda img, v, g, s: calls.append((img, s))), \
                    mock.patch.object(pipeline.image, "extract", side_effect=extract), \
                    mock.patch.object(pipeline.image, "image_exists", return_value=True) as exists, \
                    mock.patch.object(pipeline.image, "install") as install, \
                    mock.patch.object(pipeline.image, "shrink_and_check") as finish:
                exists.side_effect = lambda _img, path: path in ("exec", "init")
                report = []
                pipeline.build(source, output, apk, daemon, vendor, hal, "secilc", ir=True,
                               xrz=True, reduction=True, bridge=True, enforcing=True, report=report,
                               strict_verification=True)
            self.assertEqual(calls, [(output, "base"), (output, "bridge"), (output, "daemon")])
            self.assertEqual([item["tool"] for item in report], [
                "patch-gsi.py", "add-ir-capture-to-gsi.py", "add-xrz-compat-to-gsi.py",
                "add-phh-reduction-to-gsi.py", "eink-bridge",
                "eink-migration", "display-migration", "finalize-image",
            ])
            self.assertTrue(all(call.args[0] == output for call in install.call_args_list))
            finish.assert_called_once_with(output, strict_final=True)
            self.assertEqual(source.read_bytes(), b"fixture")
            self.assertTrue(all(item["elapsed_seconds"] >= 0 for item in report))

    def test_combined_validation_follows_finalization(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output, apk, daemon, vendor, hal = [root / n for n in
                                                        ("source", "working", "apk", "daemon", "vendor", "hal")]
            for path in (source, apk, daemon, vendor, hal):
                path.write_bytes(b"fixture")
            calls = []
            patch = SimpleNamespace(
                patch_image=lambda *a, **k: output.write_bytes(b"working"),
                validate_paths=lambda paths: None,
                validate_patched_image=lambda *args: calls.append("release"),
            )
            with mock.patch.object(pipeline.shutil, "which", return_value="/tool"), \
                    mock.patch.object(pipeline, "load", return_value=patch), \
                    mock.patch.object(pipeline.final_policy, "prepare", return_value="prepared") as prepare, \
                    mock.patch.object(pipeline.final_policy, "verify",
                                      side_effect=lambda *a, **k: calls.append("policy")) as verify, \
                    mock.patch.object(pipeline.image, "shrink_and_check",
                                      side_effect=lambda *a, **k: calls.append("finalize")), \
                    mock.patch.object(pipeline.image, "check_final_filesystem",
                                      side_effect=lambda *a, **k: calls.append("filesystem")):
                report = []
                pipeline.build(source, output, apk, daemon, vendor, hal, "secilc", ir=True,
                               xrz=True, reduction=True, bridge=True, enforcing=True, report=report)
            self.assertEqual(calls, ["finalize", "policy", "release", "filesystem"])
            self.assertEqual(verify.call_args.args[4], "prepared")
            self.assertEqual(prepare.call_count, 1)
            self.assertEqual([entry["tool"] for entry in report], [
                "patch-gsi.py", "prepare-combined-policy", "finalize-image",
                "verify-combined-policy", "verify-release", "verify-filesystem",
            ])

    def test_combined_validation_failure_prevents_final_filesystem_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / n for n in ("source", "apk", "daemon", "vendor", "hal")]
            for path in paths:
                path.write_bytes(b"fixture")
            patch = SimpleNamespace(patch_image=lambda *a, **k: None, validate_paths=lambda paths: None)
            with mock.patch.object(pipeline.shutil, "which", return_value="/tool"), \
                    mock.patch.object(pipeline, "load", return_value=patch), \
                    mock.patch.object(pipeline.final_policy, "prepare", return_value="prepared"), \
                    mock.patch.object(pipeline.final_policy, "verify", side_effect=ValueError("bad final policy")), \
                    mock.patch.object(pipeline.image, "shrink_and_check"), \
                    mock.patch.object(pipeline.image, "check_final_filesystem") as finish, \
                    self.assertRaisesRegex(ValueError, "bad final policy"):
                pipeline.build(paths[0], root / "output", paths[1], paths[2], paths[3], paths[4],
                               "secilc", ir=True, xrz=True, reduction=True, bridge=True,
                               enforcing=True, report=[])
            finish.assert_not_called()

    def test_stage_error_prevents_finalization(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source", root / "working"
            source.write_bytes(b"source")
            for name in ("apk", "daemon"):
                (root / name).write_bytes(b"file")
            patch = SimpleNamespace(patch_image=lambda *a, **k: output.write_bytes(b"working"),
                                    validate_paths=lambda paths: None)
            xrz = SimpleNamespace(prepare_compatibility=mock.Mock(side_effect=ValueError("bad policy")))
            with mock.patch.object(pipeline.shutil, "which", return_value="/tool"), \
                    mock.patch.object(pipeline, "load", side_effect=lambda _name, file:
                                   patch if file == "patch-gsi.py" else xrz), \
                    mock.patch.object(pipeline.image, "shrink_and_check") as finish, \
                    self.assertRaisesRegex(ValueError, "bad policy"):
                pipeline.build(source, output, root / "apk", root / "daemon", root / "vendor",
                               None, "secilc", ir=False, xrz=True, reduction=False,
                               bridge=False, enforcing=False, report=[])
            finish.assert_not_called()
            self.assertEqual(source.read_bytes(), b"source")


if __name__ == "__main__":
    unittest.main()
