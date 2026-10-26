import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
PATCHER = ROOT / "tools/patch-gsi.sh"


class ToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for tool in ("debugfs", "mke2fs", "e2fsck", "resize2fs", "dumpe2fs"):
            if not shutil.which(tool):
                raise unittest.SkipTest(f"Missing {tool}")

    def setUp(self):
        (ROOT / "build").mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix="tools-test-", dir=ROOT / "build")
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.base = self.work / "base image.img"
        subprocess.run(["truncate", "-s", "32M", self.base], check=True)
        subprocess.run(["mke2fs", "-q", "-t", "ext4", "-F", self.base], check=True)
        for directory in ("system", "system/etc", "system/etc/init", "system/bin",
                          "system/etc/permissions", "system/priv-app"):
            self.debug(f"mkdir {directory}", write=True)
        rc = self.work / "vndk.rc"
        rc.write_text("service phh /system/bin/true\n    seclabel u:r:phhsu_daemon:s0\n")
        self.debug(f'write "{rc}" system/etc/init/vndk.rc', write=True)
        self.apk = self.work / "test apk"
        self.apk.write_bytes(b"test-apk-payload")
        self.daemon = self.work / "test daemon"
        self.daemon.write_bytes(b"test-daemon-payload")
        self.out = self.work / "patched image.img"

    def debug(self, command, write=False, image=None):
        return subprocess.run(["debugfs", *(["-w"] if write else []), "-R", command,
                               image or self.base], check=True, capture_output=True)

    def patch(self, *extra):
        return subprocess.run(["bash", PATCHER, self.base, self.out, self.apk, self.daemon,
                               *extra], capture_output=True, text=True)

    def test_image_roundtrip_and_refuse_overwrite(self):
        original = self.base.read_bytes()
        result = self.patch()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.base.read_bytes(), original)
        files = {
            "system/bin/a9_eink_server": self.daemon,
            "system/priv-app/HiBreakEink/HiBreakEink.apk": self.apk,
            "system/bin/hibreak-wake-cycle.sh": ROOT / "tools/display/hibreak-wake-cycle.sh",
            "system/etc/init/hibreak-display.rc": ROOT / "tools/display/hibreak-display.rc",
        }
        for dest, expected in files.items():
            dumped = self.work / "dump"
            self.debug(f'dump {dest} "{dumped}"', image=self.out)
            self.assertEqual(dumped.read_bytes(), expected.read_bytes())
        self.assertNotEqual(self.patch().returncode, 0)

    def test_bad_public_key_rejected_before_output(self):
        key = self.work / "wrong key"
        key.write_text("-----BEGIN PRIVATE KEY-----\n")
        result = self.patch(key)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.out.exists())

    def test_can_update_previously_patched_image(self):
        result = self.patch()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.base = self.out
        self.out = self.work / "updated image.img"
        result = self.patch()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_sparse_or_non_ext4_rejected(self):
        self.base.write_bytes(b"not an ext4 filesystem")
        self.assertNotEqual(self.patch().returncode, 0)
        self.assertFalse(self.out.exists())

    def test_optional_adb_key_label_and_symlink_replacement(self):
        import base64
        import struct
        key = self.work / "adbkey.pub"
        key.write_text(base64.b64encode(struct.pack("<I", 64) + bytes(520)).decode() + " test@host\n")
        self.debug("symlink adb_keys /product/etc/security/adb_keys", write=True)
        result = self.patch(key)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        stat = self.debug("stat adb_keys", image=self.out).stdout.decode()
        self.assertIn("Type: regular", stat)
        self.assertIn("u:object_r:adb_keys_file:s0", stat)
        dumped = self.work / "key-check"
        self.debug(f'dump adb_keys "{dumped}"', image=self.out)
        self.assertEqual(dumped.read_bytes(), key.read_bytes())

    def test_flash_defaults_to_dry_run(self):
        result = subprocess.run(["bash", ROOT / "tools/flash-system.sh", self.base, "a"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Nothing was executed", result.stdout)
        self.assertIn("fastboot -S 64M flash system_a", result.stdout)
        self.assertNotIn("fastboot -w", result.stdout)

    def test_flash_wipe_data_is_opt_in_and_visible_in_preview(self):
        result = subprocess.run(
            ["bash", ROOT / "tools/flash-system.sh", self.base, "a", "--wipe-data"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = result.stdout.splitlines()
        flash_command = next(command for command in commands
                             if command.startswith("fastboot -S 64M flash system_a "))
        self.assertLess(commands.index(flash_command),
                        commands.index("fastboot -w"))
        self.assertLess(commands.index("fastboot -w"),
                        commands.index("fastboot reboot"))
        self.assertIn("erases shared userdata", result.stdout)
        self.assertIn("Nothing was executed", result.stdout)
        duplicate = subprocess.run(
            ["bash", ROOT / "tools/flash-system.sh", self.base, "a",
             "--wipe-data", "--wipe-data"],
            capture_output=True, text=True)
        self.assertNotEqual(duplicate.returncode, 0)

    def test_flash_refuses_wrong_device_mode_or_slot(self):
        fake_bin = self.work / "bin"
        fake_bin.mkdir()
        fastboot = fake_bin / "fastboot"
        fastboot.write_text("""#!/bin/sh
echo "$*" >> "$COMMAND_LOG"
case "$*" in
    "getvar is-userspace") echo "is-userspace: $FAKE_FASTBOOTD" >&2 ;;
    "getvar current-slot") echo "current-slot: $FAKE_SLOT" >&2 ;;
    *) exit 99 ;;
esac
""")
        fastboot.chmod(0o755)
        command_log = self.work / "commands"
        for fastbootd, slot in (("no", "a"), ("yes", "b")):
            env = dict(os.environ, PATH=f"{fake_bin}:{os.environ['PATH']}",
                       COMMAND_LOG=str(command_log), FAKE_FASTBOOTD=fastbootd,
                       FAKE_SLOT=slot)
            result = subprocess.run(
                ["bash", ROOT / "tools/flash-system.sh", self.base, "a", "--flash"],
                capture_output=True, text=True, env=env)
            self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("flash ", command_log.read_text())

    def test_flash_uses_small_chunks_and_only_reboots_on_success(self):
        fake_bin = self.work / "bin"
        fake_bin.mkdir()
        fastboot = fake_bin / "fastboot"
        fastboot.write_text("""#!/bin/sh
echo "$*" >> "$COMMAND_LOG"
case "$*" in
    "getvar is-userspace") echo "is-userspace: yes" >&2 ;;
    "getvar current-slot") echo "current-slot: a" >&2 ;;
    "-S 64M flash system_a "*) exit "$FAKE_FLASH_STATUS" ;;
    "-w") exit "$FAKE_WIPE_STATUS" ;;
    "reboot") exit 0 ;;
    *) exit 99 ;;
esac
""")
        fastboot.chmod(0o755)
        command_log = self.work / "commands"
        for status, wipe_status, wipe_requested in (
                (0, 0, False), (1, 0, False), (0, 0, True), (0, 1, True)):
            with self.subTest(flash_status=status, wipe_status=wipe_status,
                              wipe_requested=wipe_requested):
                command_log.write_text("")
                env = dict(os.environ, PATH=f"{fake_bin}:{os.environ['PATH']}",
                           COMMAND_LOG=str(command_log), FAKE_FLASH_STATUS=str(status),
                           FAKE_WIPE_STATUS=str(wipe_status))
                args = ["bash", ROOT / "tools/flash-system.sh", self.base, "a"]
                if wipe_requested:
                    args.append("--wipe-data")
                args.append("--flash")
                result = subprocess.run(
                    args,
                    capture_output=True, text=True, env=env)
                expected_status = status or (wipe_status if wipe_requested else 0)
                self.assertEqual(result.returncode, expected_status, result.stderr)
                commands = command_log.read_text().splitlines()
                self.assertIn(f"-S 64M flash system_a {self.base}", commands)
                self.assertEqual("-w" in commands, wipe_requested and status == 0)
                self.assertEqual("reboot" in commands, expected_status == 0)
                if status:
                    self.assertIn("Do not reboot", result.stderr)
                if wipe_requested and wipe_status:
                    self.assertIn("userdata wipe failed", result.stderr)


class BootWakeTests(unittest.TestCase):
    def test_default_wakes_without_sleep_and_legacy_cycle_is_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            calls = work / "calls"
            for name in ("input", "sleep", "log", "hibreak-disable-hwc.sh"):
                executable = work / name
                executable.write_text(f'#!/bin/sh\nprintf "%s\\n" "{name} $*" >> "$CALLS"\n')
                executable.chmod(0o755)
            getprop = work / "getprop"
            getprop.write_text('#!/bin/sh\nprintf "%s\\n" "$BOOT_SLEEP_CYCLE"\n')
            getprop.chmod(0o755)
            source = (ROOT / "tools/display/hibreak-wake-cycle.sh").read_text()
            # Replace only the Android absolute executable path for host mocks.
            source = source.replace("/system/bin/hibreak-disable-hwc.sh", "hibreak-disable-hwc.sh")
            for option in ("", "false", "true"):
                calls.write_text("")
                env = dict(os.environ, PATH=f"{work}:{os.environ['PATH']}",
                           CALLS=str(calls), BOOT_SLEEP_CYCLE=option)
                result = subprocess.run(["sh"], input=source, capture_output=True,
                                        text=True, env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                recorded = calls.read_text()
                self.assertIn("input keyevent KEYCODE_WAKEUP", recorded)
                self.assertEqual("input keyevent KEYCODE_SLEEP" in recorded, option == "true")
                self.assertEqual(recorded.count("hibreak-disable-hwc.sh"), 2)


if __name__ == "__main__":
    unittest.main()
