import importlib.util
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("phh_reduction", ROOT / "tools/image/add-phh-reduction-to-gsi.py")
overlay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(overlay)


class PhhReductionTests(unittest.TestCase):
    def test_ext4_roundtrip_preserves_source_and_installs_both_policy_files(self):
        for tool in ("debugfs", "mke2fs", "e2fsck", "resize2fs", "dumpe2fs"):
            if not shutil.which(tool):
                self.skipTest(f"Missing {tool}")
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            source, output = work / "source.img", work / "output.img"
            with source.open("wb") as stream:
                stream.truncate(32 * 1024 * 1024)
            subprocess.run(["mke2fs", "-q", "-t", "ext4", "-F", source], check=True)
            for path in ("system", "system/etc", "system/etc/selinux",
                         "system/system_ext", "system/system_ext/etc",
                         "system/system_ext/etc/selinux"):
                overlay.image.run("debugfs", "-w", "-R", f"mkdir {path}", str(source))
            ext, digest = work / "ext", work / "digest"
            ext.write_bytes(b"reduced policy\n")
            digest.write_bytes(b"updated digest\n")
            original = source.read_bytes()
            overlay.build_image(source, output, (ext, digest), work)
            self.assertEqual(source.read_bytes(), original)
            for index, (file, destination) in enumerate((
                (ext, overlay.EXT_POLICY),
                (digest, f"{overlay.image.POLICY}/plat_sepolicy_and_mapping.sha256"),
            )):
                extracted = overlay.image.extract(output, destination, work / f"check-{index}")
                self.assertEqual(extracted.read_bytes(), file.read_bytes())

    def test_exact_policy_required(self):
        with self.assertRaisesRegex(ValueError, "Unsupported system-ext policy"):
            overlay.reduce_policy(b"(allow phhsu_daemon property_type (property_service (set)))\n")

    def test_removes_only_selected_complete_grants(self):
        content = ("(typepermissive phhsu_daemon)\n"
                   "(allow phhsu_daemon property_type (property_service (set)))\n"
                   "(neverallow a b (file (read)))\n"
                   "(allow shell b (file (read)))\n").encode()
        digest = overlay.hashlib.sha256(content).hexdigest()
        with mock.patch.object(overlay, "EXT_SHA256", digest), \
                mock.patch.object(overlay, "REMOVED_LINES", frozenset((2,))):
            reduced = overlay.reduce_policy(content)
        self.assertEqual(reduced, content.replace(
            b"(allow phhsu_daemon property_type (property_service (set)))\n",
            b"; experiment removed grant\n",
        ))
        for number in (1, 3, 4):
            with mock.patch.object(overlay, "EXT_SHA256", digest), \
                    mock.patch.object(overlay, "REMOVED_LINES", frozenset((number,))):
                with self.assertRaisesRegex(ValueError, "Unexpected PHH grant"):
                    overlay.reduce_policy(content)

    def test_unexpected_conflict_count_is_rejected_before_runtime_compile(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            ext = work / "ext.cil"
            ext.write_bytes(b"fixture")
            with mock.patch.object(overlay, "prepare_ir_policy", return_value=(None, None, [ext])), \
                    mock.patch.object(overlay, "reduce_policy", return_value=b"reduced"), \
                    mock.patch.object(overlay.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"", b"")), \
                    mock.patch.object(overlay.image, "run") as runtime:
                with self.assertRaisesRegex(ValueError, "Unexpected reduced policy conflicts"):
                    overlay.prepare_reduction(Path("base"), Path("vendor"), work, "secilc")
                runtime.assert_not_called()

    def test_failed_image_validation_removes_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            output = work / "output.img"
            def copy(_source, destination, _headroom):
                destination.write_bytes(b"partial")
            with mock.patch.object(overlay.image, "copy_and_grow", side_effect=copy), \
                    mock.patch.object(overlay.image, "install"), \
                    mock.patch.object(overlay.image, "shrink_and_check", side_effect=ValueError("invalid image")):
                with self.assertRaisesRegex(ValueError, "invalid image"):
                    overlay.build_image(Path("source"), output, (work / "ext", work / "digest"), work)
            self.assertFalse(output.exists())

    def test_existing_image_is_not_deleted_or_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            output = work / "existing.img"
            output.write_bytes(b"keep")
            with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                overlay.build_image(Path("source"), output, (work / "ext", work / "digest"), work)
            self.assertEqual(output.read_bytes(), b"keep")
