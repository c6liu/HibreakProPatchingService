import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from tools.hibreak import final_policy


class FinalPolicyTests(unittest.TestCase):
    def test_final_filesystem_check_rejects_repaired_or_failed_checks(self):
        for returncode in (1, 4):
            with self.subTest(returncode=returncode), \
                    mock.patch.object(final_policy.image.subprocess, "run",
                                      return_value=subprocess.CompletedProcess(
                                          ["e2fsck"], returncode, b"filesystem problem", b"")), \
                    self.assertRaisesRegex(ValueError, "Final filesystem check failed"):
                final_policy.image.check_final_filesystem(Path("image"))

    def test_final_diagnostics_reject_new_conflicts(self):
        baseline = {"existing"}
        final_policy.validate_final_conflicts(baseline, {"existing"})
        final_policy.validate_final_conflicts(baseline, set())
        with self.assertRaisesRegex(ValueError, "Combined policy adds neverallow diagnostics"):
            final_policy.validate_final_conflicts(baseline, {"existing", "new"})

    def test_final_contents_and_metadata_are_checked_before_compilation(self):
        digest = hashlib.sha256(b"expected").hexdigest()
        prepared = ({"system/file": (digest, "0644", "u:object_r:system_file:s0")},
                    [], [], set(), set(), set(), {}, set(), set(), set(), set(), None)
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            content = [b"expected"]
            stat = ["Mode:  0644 User:     0   Group:     0 u:object_r:system_file:s0"]

            def extract(_image, _path, destination):
                destination.write_bytes(content[0])
                return destination

            def run(*args):
                if "stat system/priv-app/HiBreakEink" in args:
                    return SimpleNamespace(stdout=(
                        b"Mode:  0755 User:     0   Group:     0 u:object_r:system_file:s0"))
                return SimpleNamespace(stdout=stat[0].encode())

            with mock.patch.dict(sys.modules, {"setools": SimpleNamespace(SELinuxPolicy=object())}), \
                    mock.patch.object(final_policy.image, "extract", side_effect=extract), \
                    mock.patch.object(final_policy.image, "run", side_effect=run):
                content[0] = b"corrupted"
                with self.assertRaisesRegex(ValueError, "content mismatch"):
                    final_policy.verify(Path("image"), Path("vendor"), "secilc", work,
                                        prepared, parallel_compile=False)
                content[0] = b"expected"
                for bad_stat in ("Mode:  0600 User:     0   Group:     0 u:object_r:system_file:s0",
                                 "Mode:  0644 User:     1   Group:     0 u:object_r:system_file:s0",
                                 "Mode:  0644 User:     0   Group:     0 u:object_r:wrong:s0"):
                    stat[0] = bad_stat
                    with self.subTest(stat=bad_stat), self.assertRaisesRegex(ValueError, "metadata mismatch"):
                        final_policy.verify(Path("image"), Path("vendor"), "secilc", work,
                                            prepared, parallel_compile=False)


if __name__ == "__main__":
    unittest.main()
