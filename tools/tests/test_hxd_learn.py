import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class HxdLearnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("cc")
        if not compiler:
            raise unittest.SkipTest("Missing host C compiler")
        cls.build = tempfile.TemporaryDirectory(prefix="hxd-learn-test-")
        cls.addClassCleanup(cls.build.cleanup)
        cls.binary = Path(cls.build.name) / "mock-hxd-learn"
        subprocess.run(
            [compiler, "-std=c11", "-D_DEFAULT_SOURCE", "-Wall", "-Wextra", "-Werror",
             ROOT / "tools/tests/native/hxd_learn_mock.c", "-o", cls.binary],
            check=True,
        )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hxd-record-")
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name) / "tv.bin"

    def run_tool(self, scenario, *args):
        return subprocess.run(
            [self.binary, *args],
            env={**os.environ, "HXD_TEST_SCENARIO": scenario, "HXD_TEST_SERVICE_DIR": self.tmp.name},
            text=True, capture_output=True, timeout=5,
        )

    def test_lossless_extended_and_short(self):
        for short in (False, True):
            with self.subTest(short=short):
                result = self.run_tool(
                    "success", "capture", *(["--short"] if short else []), str(self.output),
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                length = 110 if short else 230
                self.assertEqual(self.output.read_bytes(), bytes(range(length)))
                self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)
                self.assertIn(f"Saved {length}", result.stdout)
                self.assertIn("NOT a transmit packet", result.stderr)
                self.assertIn("discards the receive checksum", result.stderr)
                self.output.unlink()

    def test_not_ready_poll_and_partial_local_save(self):
        for scenario in ("delayed", "save-partial"):
            result = self.run_tool(scenario, "capture", str(self.output))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.output.read_bytes(), bytes(range(230)))
            self.output.unlink()

    def test_failures_remove_output(self):
        cases = {
            "open-denied": "SELinux",
            "not-char": "not a character device",
            "busy": "lock /dev/ctrl",
            "write-error": "not retried",
            "write-partial": "Incomplete learning command",
            "write-interrupted": "not retried",
            "read-error": "nonzero controller status",
            "read-partial": "refusing to pad or combine",
            "bad-status": "Invalid learned record",
            "all-zero": "Invalid learned record",
            "no-signal": "matches the observed no-button control exactly",
            "timeout": "timed out",
            "late": "deadline expired during read",
            "cancel": "interrupted by signal",
            "save-error": "write capture file",
            "save-zero": "write returned zero",
            "fsync-error": "fsync capture file",
        }
        for scenario, message in cases.items():
            with self.subTest(scenario=scenario):
                result = self.run_tool(
                    scenario, "capture", "--timeout", "1", str(self.output),
                )
                self.assertEqual(result.returncode, 130 if scenario == "cancel" else 1, result.stderr)
                self.assertIn(message, result.stderr)
                self.assertFalse(self.output.exists())
                self.assertNotIn("Saved", result.stdout)

    def test_usage_does_not_open_device(self):
        for args in (
            [], ["replay", str(self.output)], ["capture"],
            ["capture", "--unknown", str(self.output)],
            ["capture", "--short", "--short", str(self.output)],
            ["capture", "--timeout", "2", "--timeout", "3", str(self.output)],
        ):
            result = self.run_tool("no-device", *args)
            self.assertEqual(result.returncode, 2, result.stderr)
        result = self.run_tool("no-device", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("never an IR replay", result.stdout)
        self.assertFalse(self.output.exists())

    def test_invalid_timeouts_before_device_access(self):
        for value in ("0", "61", "-1", "2.5", "x", "", " 2", "+2", "9999999999999999999999"):
            result = self.run_tool("no-device", "capture", "--timeout", value, str(self.output))
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("Timeout must be", result.stderr)
            self.assertFalse(self.output.exists())

    def test_existing_file_and_symlink_are_untouched(self):
        self.output.write_bytes(b"keep")
        result = self.run_tool("no-device", "capture", str(self.output))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.output.read_bytes(), b"keep")
        link = self.output.with_name("link")
        link.symlink_to(self.output)
        result = self.run_tool("no-device", "capture", str(link))
        self.assertEqual(result.returncode, 1)
        self.assertTrue(link.is_symlink())
        self.assertEqual(self.output.read_bytes(), b"keep")

    def test_missing_parent_before_device_access(self):
        result = self.run_tool("no-device", "capture", str(self.output / "missing"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("create capture file", result.stderr)

    def test_service_replaces_only_fixed_record_and_reports_result(self):
        record = Path(self.tmp.name) / "record.bin"
        log = Path(self.tmp.name) / "result.txt"
        for scenario in ("success", "timeout", "open-denied", "no-signal", "cancel", "success"):
            record.write_bytes(b"old capture")
            result = self.run_tool(scenario, "--service")
            self.assertEqual(result.returncode, 0 if scenario == "success" else 130 if scenario == "cancel" else 1)
            self.assertIn(f"Capture service exit status: {result.returncode}", log.read_text())
            self.assertEqual(log.stat().st_mode & 0o777, 0o600)
            if scenario == "success":
                self.assertEqual(record.read_bytes(), bytes(range(230)))
                self.assertEqual(record.stat().st_mode & 0o777, 0o600)
            else:
                self.assertFalse(record.exists())
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "")

    def test_service_mode_selection_and_rejection_before_access(self):
        record = Path(self.tmp.name) / "record.bin"
        for mode, length in (("short", 110), ("extended", 230)):
            result = self.run_tool("success", "--service", mode)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(record.read_bytes(), bytes(range(length)))
        for args in (["--service", "invalid"], ["--service", "short", "extra"], ["--service", "/dev/ctrl"]):
            result = self.run_tool("no-device", *args)
            self.assertEqual(result.returncode, 2)
            self.assertIn("Service mode must be", result.stderr)
            self.assertEqual(record.read_bytes(), bytes(range(230)))

    def test_no_signal_rejection_is_exact_not_a_header_heuristic(self):
        result = self.run_tool("near-no-signal", "capture", str(self.output))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.stat().st_size, 230)
        self.assertEqual(self.output.read_bytes()[-1], 0x50)
        self.assertIn("candidate only", result.stderr)

    def test_service_log_symlink_refused_before_device_access(self):
        target = Path(self.tmp.name) / "keep"
        target.write_text("unchanged")
        (Path(self.tmp.name) / "result.txt").symlink_to(target)
        result = self.run_tool("no-device", "--service")
        self.assertEqual(result.returncode, 1)
        self.assertIn("open capture service result", result.stderr)
        self.assertEqual(target.read_text(), "unchanged")

    def test_bounded_transmit_test_and_abort_without_retry(self):
        record = Path(self.tmp.name) / "record.bin"
        record.write_bytes(b"keep learning record")
        for scenario, expected in (("tx-success", 0), ("tx-error", 1), ("tx-partial", 1), ("tx-cancel", 143)):
            with self.subTest(scenario=scenario):
                result = self.run_tool(scenario, "--service", "tx-test")
                self.assertEqual(result.returncode, expected, result.stderr)
                log = (Path(self.tmp.name) / "result.txt").read_text()
                self.assertIn(f"Transmit test service exit status: {expected}", log)
                self.assertIn("Unknown appliance action", log)
                self.assertEqual(record.read_bytes(), b"keep learning record")
                if expected == 0:
                    self.assertIn("write 5/5 completed", log)
                    self.assertIn("optical output is NOT verified", log)
                elif scenario != "tx-cancel":
                    self.assertIn("not retried", log)


if __name__ == "__main__":
    unittest.main()
