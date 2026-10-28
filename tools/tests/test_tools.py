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
        build_prop = self.work / "build.prop"
        build_prop.write_text("ro.debuggable=0\nro.secure=1\npersist.sys.usb.config=adb\n")
        self.debug(f'write "{build_prop}" system/build.prop', write=True)
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

    def read_image_text(self, path):
        result = subprocess.run(["debugfs", "-R", f"cat {path}", self.out],
                                check=True, capture_output=True, text=True)
        return result.stdout

    def test_image_roundtrip_and_refuse_overwrite(self):
        original = self.base.read_bytes()
        result = self.patch()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.base.read_bytes(), original)
        files = {
            "system/bin/a9_eink_server": self.daemon,
            "system/priv-app/HiBreakEink/HiBreakEink.apk": self.apk,
            "system/bin/hibreak-disable-hwc.sh": ROOT / "tools/display/hibreak-disable-hwc.sh",
            "system/bin/hibreak-aod.sh": ROOT / "tools/display/hibreak-aod.sh",
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
        old_helper = self.work / "old-adb-helper"
        old_helper.write_text("settings put global adb_enabled 1\n")
        self.debug(f'write "{old_helper}" system/bin/hibreak-enable-adb.sh', write=True)
        old_wake_helper = self.work / "old-wake-helper"
        old_wake_helper.write_text("input keyevent KEYCODE_WAKEUP\n")
        self.debug(f'write "{old_wake_helper}" system/bin/hibreak-wake-cycle.sh', write=True)
        result = self.patch()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Inode:", self.debug(
            "stat system/bin/hibreak-enable-adb.sh", image=self.out).stdout.decode())
        self.assertEqual(self.read_image_text("system/bin/hibreak-wake-cycle.sh"),
                         (ROOT / "tools/display/hibreak-wake-cycle.sh").read_text())
        self.base = self.out
        self.out = self.work / "updated image.img"
        result = self.patch()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_all_builds_preserve_saved_adb_state(self):
        for release in (False, True):
            with self.subTest(release=release):
                self.out = self.work / f"preserve-adb-{release}.img"
                result = self.patch(*(["--release"] if release else []))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                display = self.read_image_text("system/etc/init/hibreak-display.rc")
                self.assertNotIn("setprop persist.sys.usb.config", display)
                self.assertNotIn("setprop sys.usb.config", display)
                self.assertNotIn("hibreak_enable_adb", display)
                self.assertIn("service hibreak_wake_cycle", display)
                self.assertEqual(self.read_image_text("system/bin/hibreak-wake-cycle.sh"),
                                 (ROOT / "tools/display/hibreak-wake-cycle.sh").read_text())
                for prop in ("persist.sys.phh.enable_sf_gl_backpressure",
                             "persist.sys.phh.enable_sf_hwc_backpressure",
                             "debug.sf.enable_gl_backpressure",
                             "debug.sf.enable_hwc_backpressure"):
                    self.assertIn(f"setprop {prop} false", display)
                self.assertIn("on property:init.svc.surfaceflinger=running\n"
                              "    start hibreak_disable_hwc", display)
                self.assertIn("on property:sys.boot_completed=1\n"
                              "    start hibreak_disable_hwc\n"
                              "    start hibreak_wake_cycle\n"
                              "    start hibreak_aod_setup", display)
                self.assertIn("persist.sys.usb.config=mtp\n",
                              self.read_image_text("system/build.prop"))
                self.assertNotIn("Inode:", self.debug(
                    "stat system/bin/hibreak-enable-adb.sh", image=self.out).stdout.decode())

    def test_sparse_or_non_ext4_rejected(self):
        self.base.write_bytes(b"not an ext4 filesystem")
        self.assertNotEqual(self.patch().returncode, 0)
        self.assertFalse(self.out.exists())

    def test_missing_usb_default_is_added(self):
        for release in (False, True):
            for suffix in ("", "\n"):
                with self.subTest(release=release, suffix=suffix):
                    self.out = self.work / f"missing-usb-{release}-{len(suffix)}.img"
                    original = "ro.debuggable=1\nro.secure=1\n# end of file" + suffix
                    build_prop = self.work / "build.prop"
                    build_prop.write_text(original)
                    self.debug("rm system/build.prop", write=True)
                    self.debug(f'write "{build_prop}" system/build.prop', write=True)
                    result = self.patch(*(["--release"] if release else []))
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual(self.read_image_text("system/build.prop"),
                                     original.rstrip("\n") +
                                     "\npersist.sys.usb.config=mtp\n")

    def test_external_storage_property_is_not_added(self):
        result = self.patch()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("external_storage.sdcardfs.enabled",
                         self.read_image_text("system/build.prop"))

    def add_lineage_layout(self):
        for directory in ("system/system_ext", "system/system_ext/etc", "system/xbin"):
            self.debug(f"mkdir {directory}", write=True)
        system_ext = self.work / "system_ext.prop"
        system_ext.write_text("ro.adb.secure=0\nro.face.sense_service=true\n"
                              "persist.sys.usb.config=adb\n# end of file\n")
        self.debug(f'write "{system_ext}" system/system_ext/etc/build.prop', write=True)
        su = self.work / "su"
        su.write_bytes(b"su-binary")
        self.debug(f'write "{su}" system/xbin/su', write=True)
        return system_ext.read_text()

    def test_lineage_adb_auth_usb_default_and_root_removed(self):
        original = self.add_lineage_layout()
        for release in (False, True):
            with self.subTest(release=release):
                self.out = self.work / f"lineage-{release}.img"
                result = self.patch(*(["--release"] if release else []))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(
                    self.read_image_text("system/system_ext/etc/build.prop"),
                    original.replace("ro.adb.secure=0", "ro.adb.secure=1").replace(
                        "persist.sys.usb.config=adb", "persist.sys.usb.config=mtp"))
                self.assertIn("persist.sys.usb.config=mtp\n",
                              self.read_image_text("system/build.prop"))
                self.assertNotIn("Inode:", self.debug(
                    "stat system/xbin/su", image=self.out).stdout.decode())

    def test_root_flag_keeps_su(self):
        self.add_lineage_layout()
        result = self.patch("--release", "--root")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Root kept", result.stdout)
        self.assertEqual(self.read_image_text("system/xbin/su"), "su-binary")
        self.assertIn("ro.adb.secure=1\n",
                      self.read_image_text("system/system_ext/etc/build.prop"))
        self.out = self.work / "duplicate-root.img"
        result = self.patch("--root", "--root")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Duplicate option: --root", result.stderr)
        self.assertFalse(self.out.exists())

    def test_duplicate_usb_defaults_are_rejected(self):
        build_prop = self.work / "build.prop"
        build_prop.write_text("persist.sys.usb.config=adb\npersist.sys.usb.config=mtp\n")
        self.debug("rm system/build.prop", write=True)
        self.debug(f'write "{build_prop}" system/build.prop', write=True)
        result = self.patch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("persist.sys.usb.config", result.stderr)
        self.assertNotIn("Verified image ready", result.stdout)

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

    def test_release_mode_preserves_adb_and_disables_diagnostic_hooks(self):
        result = self.patch("--release")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        display = self.read_image_text("system/etc/init/hibreak-display.rc")
        eink = self.read_image_text("system/etc/init/a9_eink_gsi.rc")
        self.assertNotIn("setprop persist.sys.usb.config", display)
        self.assertNotIn("setprop sys.usb.config", display)
        self.assertNotIn("mtp,adb", display)
        self.assertNotIn("hibreak_enable_adb", display)
        self.assertNotIn("debug.hibreak", display)
        self.assertIn("service hibreak_aod_doze", display)
        self.assertIn("service hibreak_wake_cycle", display)
        self.assertNotIn("debug.hibreak", eink)
        self.assertIn("service a9_eink_server", eink)
        build_prop = self.read_image_text("system/build.prop")
        self.assertIn("persist.sys.usb.config=mtp", build_prop)
        self.assertNotIn("persist.sys.usb.config=adb", build_prop)
        adb_script_stat = self.debug("stat system/bin/hibreak-enable-adb.sh",
                                     image=self.out).stdout.decode()
        self.assertNotIn("Inode:", adb_script_stat)
        self.assertNotIn(
            "system/bin/hibreak-enable-adb.sh",
            self.debug("ls system/bin", image=self.out).stdout.decode(),
        )
        rejected = subprocess.run(
            ["bash", PATCHER, self.base, self.work / "release-with-key.img",
             self.apk, self.daemon, self.work / "host-key.pub", "--release"],
            capture_output=True, text=True)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("cannot be combined", rejected.stderr)

    def test_flash_defaults_to_dry_run(self):
        result = subprocess.run(["bash", ROOT / "tools/flash-system.sh", self.base, "a"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Nothing was executed", result.stdout)
        self.assertIn("fastboot flash system_a", result.stdout)
        self.assertNotIn("fastboot -w", result.stdout)

    def test_flash_wipe_data_is_opt_in_and_visible_in_preview(self):
        result = subprocess.run(
            ["bash", ROOT / "tools/flash-system.sh", self.base, "a", "--wipe-data"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = result.stdout.splitlines()
        flash_command = next(command for command in commands
                             if command.startswith("fastboot flash system_a "))
        self.assertLess(commands.index(flash_command),
                        commands.index("fastboot reboot bootloader"))
        self.assertLess(commands.index("fastboot reboot bootloader"),
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

    def test_flash_stock_partition_deletion_is_opt_in_and_ordered(self):
        preview = subprocess.run(
            ["bash", ROOT / "tools/flash-system.sh", self.base, "a",
             "--delete-stock-logical-partitions"],
            capture_output=True, text=True)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        commands = preview.stdout.splitlines()
        product = "fastboot delete-logical-partition product_a"
        system_ext = "fastboot delete-logical-partition system_ext_a"
        flash = next(command for command in commands
                     if command.startswith("fastboot flash system_a "))
        self.assertLess(commands.index(product), commands.index(system_ext))
        self.assertLess(commands.index(system_ext), commands.index(flash))
        self.assertIn("removes product and system_ext from slot a", preview.stdout)
        duplicate = subprocess.run(
            ["bash", ROOT / "tools/flash-system.sh", self.base, "a",
             "--delete-stock-logical-partitions",
             "--delete-stock-logical-partitions"],
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

    def test_flash_uses_fastboot_default_and_only_reboots_on_success(self):
        fake_bin = self.work / "bin"
        fake_bin.mkdir()
        fastboot = fake_bin / "fastboot"
        fastboot.write_text("""#!/bin/sh
echo "$*" >> "$COMMAND_LOG"
case "$*" in
    "getvar is-userspace")
        if [ -e "$MODE_FILE" ]; then echo "is-userspace: no" >&2
        else echo "is-userspace: yes" >&2; fi ;;
    "getvar current-slot") echo "current-slot: a" >&2 ;;
    "flash system_a "*) exit "$FAKE_FLASH_STATUS" ;;
    "reboot bootloader")
        [ "$FAKE_STAY_FASTBOOTD" = 1 ] || touch "$MODE_FILE" ;;
    "-w")
        [ -e "$MODE_FILE" ] || exit 98
        echo "wipe task partition not found: cache"
        echo "wipe task partition not found: metadata"
        echo "Finished wipe"
        exit "$FAKE_WIPE_STATUS"
        ;;
    "reboot") exit 0 ;;
    *) exit 99 ;;
esac
""")
        fastboot.chmod(0o755)
        command_log = self.work / "commands"
        mode_file = self.work / "in-bootloader"
        for status, wipe_status, wipe_requested, stay in (
                (0, 0, False, 0), (1, 0, False, 0), (0, 0, True, 0), (0, 1, True, 0),
                (0, 0, True, 1)):
            with self.subTest(flash_status=status, wipe_status=wipe_status,
                              wipe_requested=wipe_requested, stay_fastbootd=stay):
                command_log.write_text("")
                mode_file.unlink(missing_ok=True)
                env = dict(os.environ, PATH=f"{fake_bin}:{os.environ['PATH']}",
                           COMMAND_LOG=str(command_log), FAKE_FLASH_STATUS=str(status),
                           FAKE_WIPE_STATUS=str(wipe_status), MODE_FILE=str(mode_file),
                           FAKE_STAY_FASTBOOTD=str(stay))
                args = ["bash", ROOT / "tools/flash-system.sh", self.base, "a"]
                if wipe_requested:
                    args.append("--wipe-data")
                args.append("--flash")
                result = subprocess.run(
                    args,
                    capture_output=True, text=True, env=env)
                expected_status = status or (
                    (wipe_status or stay) if wipe_requested else 0)
                self.assertEqual(result.returncode, expected_status, result.stderr)
                commands = command_log.read_text().splitlines()
                self.assertIn(f"flash system_a {self.base}", commands)
                self.assertEqual("reboot bootloader" in commands,
                                 wipe_requested and status == 0)
                self.assertEqual("-w" in commands, wipe_requested and status == 0
                                 and not stay)
                if "-w" in commands:
                    self.assertLess(commands.index("reboot bootloader"),
                                    commands.index("-w"))
                self.assertEqual("reboot" in commands, expected_status == 0)
                if stay:
                    self.assertIn("not in the bootloader", result.stderr)
                if wipe_requested and not wipe_status and not stay:
                    self.assertIn("Finished wipe", result.stdout)
                    self.assertNotIn("wipe task partition not found",
                                     result.stdout + result.stderr)
                if status:
                    self.assertIn("Do not reboot", result.stderr)
                if wipe_requested and wipe_status:
                    self.assertIn("userdata wipe failed", result.stderr)
                    self.assertIn("wipe task partition not found: cache", result.stderr)

    def test_flash_deletes_requested_logical_partitions_before_flash(self):
        fake_bin = self.work / "bin"
        fake_bin.mkdir()
        fastboot = fake_bin / "fastboot"
        fastboot.write_text("""#!/bin/sh
echo "$*" >> "$COMMAND_LOG"
case "$*" in
    "getvar is-userspace") echo "is-userspace: yes" >&2 ;;
    "getvar current-slot") echo "current-slot: a" >&2 ;;
    "delete-logical-partition product_a") exit "$FAKE_DELETE_PRODUCT_STATUS" ;;
    "delete-logical-partition system_ext_a") exit "$FAKE_DELETE_SYSTEM_EXT_STATUS" ;;
    "flash system_a "*) exit 0 ;;
    "reboot") exit 0 ;;
    *) exit 99 ;;
esac
""")
        fastboot.chmod(0o755)
        command_log = self.work / "commands"
        for product_status, system_ext_status in ((0, 0), (1, 0), (0, 1)):
            with self.subTest(product_status=product_status,
                              system_ext_status=system_ext_status):
                command_log.write_text("")
                env = dict(os.environ, PATH=f"{fake_bin}:{os.environ['PATH']}",
                           COMMAND_LOG=str(command_log),
                           FAKE_DELETE_PRODUCT_STATUS=str(product_status),
                           FAKE_DELETE_SYSTEM_EXT_STATUS=str(system_ext_status))
                result = subprocess.run(
                    ["bash", ROOT / "tools/flash-system.sh", self.base, "a",
                     "--delete-stock-logical-partitions", "--flash"],
                    capture_output=True, text=True, env=env)
                commands = command_log.read_text().splitlines()
                product = "delete-logical-partition product_a"
                system_ext = "delete-logical-partition system_ext_a"
                self.assertIn(product, commands)
                if product_status:
                    self.assertNotIn(system_ext, commands)
                    self.assertNotIn(f"flash system_a {self.base}", commands)
                    self.assertNotIn("reboot", commands)
                    self.assertIn("Do not reboot", result.stderr)
                    self.assertNotEqual(result.returncode, 0)
                elif system_ext_status:
                    self.assertLess(commands.index(product), commands.index(system_ext))
                    self.assertNotIn(f"flash system_a {self.base}", commands)
                    self.assertNotIn("reboot", commands)
                    self.assertIn("preceding logical partition may already be deleted",
                                  result.stderr)
                    self.assertNotEqual(result.returncode, 0)
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    flash = f"flash system_a {self.base}"
                    self.assertLess(commands.index(product), commands.index(system_ext))
                    self.assertLess(commands.index(system_ext), commands.index(flash))
                    self.assertEqual(commands[-1], "reboot")


class RefreshModeTests(unittest.TestCase):
    def test_hd_256_reaches_driver_and_property(self):
        compiler = shutil.which("cc")
        if compiler is None:
            self.skipTest("C compiler is needed for daemon command tests")
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / "android").mkdir()
            (work / "sys").mkdir()
            (work / "android/log.h").write_text(
                "#define ANDROID_LOG_INFO 4\n#define ANDROID_LOG_ERROR 6\n"
                "int __android_log_print(int, const char *, const char *, ...);\n")
            (work / "sys/system_properties.h").write_text(
                "int __system_property_set(const char *, const char *);\n")
            binary = work / "refresh-mode-probe"
            result = subprocess.run(
                [compiler, "-Wall", "-Wextra", "-Werror", "-I", str(work),
                 ROOT / "tools/tests/native/RefreshModeProbe.c", "-o", binary],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([binary], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


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
