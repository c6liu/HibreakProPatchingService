import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest import mock

from tools.hibreak import tested_stages


class TestedStageTests(unittest.TestCase):
    def test_metadata_rejects_wrong_label_and_mode(self):
        stat = 'Type: regular Mode:  0755\nUser:     0   Group:     0\nu:object_r:system_file:s0'
        with mock.patch.object(tested_stages.image, "run",
                               return_value=CompletedProcess([], 0, stdout=stat.encode())):
            with self.assertRaisesRegex(ValueError, "eink_server"):
                tested_stages.validate_metadata(Path("source"), "daemon")
            with self.assertRaisesRegex(ValueError, "eink_gsi.rc"):
                tested_stages.validate_metadata(Path("source"), "base")

    def test_each_component_is_required_and_fingerprinted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, vendor, gsi = (root / name for name in ("source", "vendor", "gsi"))
            for path in (source, vendor, gsi):
                path.write_bytes(path.name.encode())
            expected = tested_stages.sha256(source)

            def extract(_image, _path, destination):
                destination.write_bytes(source.read_bytes())
                return destination

            with mock.patch.object(tested_stages, "GSI_SHA256", tested_stages.sha256(gsi)), \
                    mock.patch.object(tested_stages, "VENDOR_SHA256", tested_stages.sha256(vendor)), \
                    mock.patch.dict(tested_stages.COMMON, {"component": expected}, clear=True), \
                    mock.patch.dict(tested_stages.STAGES, {"base": {"other": expected}}, clear=True), \
                    mock.patch.object(tested_stages, "validate_metadata"), \
                    mock.patch.object(tested_stages.image, "image_exists", return_value=False), \
                    mock.patch.object(tested_stages.image, "extract", side_effect=extract) as extraction:
                tested_stages.validate_rebuild(source, vendor, gsi, "base")
                self.assertEqual(extraction.call_count, 2)
                source.write_bytes(b"tampered")
                with self.assertRaisesRegex(ValueError, "Unverified base image component"):
                    tested_stages.validate_rebuild(source, vendor, gsi, "base")
                vendor.write_bytes(b"other")
                with self.assertRaisesRegex(ValueError, "exact tested GSI and vendor"):
                    tested_stages.validate_rebuild(source, vendor, gsi, "base")

    def test_unexpected_product_mapping_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image"
            path.write_bytes(b"image")
            digest = tested_stages.sha256(path)
            with mock.patch.object(tested_stages, "GSI_SHA256", digest), \
                    mock.patch.object(tested_stages, "VENDOR_SHA256", digest), \
                    mock.patch.object(tested_stages, "validate_metadata"), \
                    mock.patch.object(tested_stages.image, "image_exists", return_value=True), \
                    self.assertRaisesRegex(ValueError, "product mapping"):
                tested_stages.validate_rebuild(path, path, path, "base")


if __name__ == "__main__":
    unittest.main()
