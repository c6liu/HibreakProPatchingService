import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
AOD_SCRIPT = ROOT / "tools/display/hibreak-aod.sh"
RELEASE_SCRIPT = ROOT / "tools/prepare-release-init.py"


class DisplayScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="display-script-test-")
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.bin = self.work / "bin"
        self.bin.mkdir()
        self.log = self.work / "commands.log"
        stub = self.bin / "stub"
        stub.write_text(
            "#!/usr/bin/env python3\n"
            "import os, pathlib, sys\n"
            "name = pathlib.Path(sys.argv[0]).name\n"
            "args = sys.argv[1:]\n"
            "with open(os.environ['COMMAND_LOG'], 'a') as log:\n"
            "    log.write(name + ' ' + ' '.join(args) + '\\n')\n"
            "if name == 'getprop':\n"
            "    print(os.environ.get('PROP_' + args[0], ''))\n"
            "elif name == 'cmd' and args[:2] == ['settings', 'get']:\n"
            "    print(os.environ.get('SETTING_' + args[-1], '0'))\n"
        )
        stub.chmod(0o755)
        for command in ("getprop", "cmd", "setprop", "log"):
            (self.bin / command).symlink_to(stub)

    def run_aod(self, action, values=None):
        environment = os.environ.copy()
        environment.update({
            "PATH": f"{self.bin}:{environment['PATH']}",
            "COMMAND_LOG": str(self.log),
            **(values or {}),
        })
        return subprocess.run(
            ["/bin/sh", str(AOD_SCRIPT), action],
            capture_output=True, text=True, env=environment,
        )

    def commands(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_doze_inverts_only_when_aod_is_enabled_and_not_already_inverted(self):
        result = self.run_aod(
            "doze", {
                "PROP_persist.sys.hibreak.aod_invert": "true",
                "SETTING_doze_always_on": "1",
                "SETTING_accessibility_display_inversion_enabled": "0",
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("setprop persist.sys.hibreak.aod_inverted 1", self.commands())
        self.assertIn("cmd settings put secure accessibility_display_inversion_enabled 1",
                      self.commands())

    def test_doze_preserves_user_enabled_inversion(self):
        result = self.run_aod(
            "doze", {
                "PROP_persist.sys.hibreak.aod_invert": "true",
                "SETTING_doze_always_on": "1",
                "SETTING_accessibility_display_inversion_enabled": "1",
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(command.startswith("setprop ") for command in self.commands()))

    def test_wake_restores_only_inversion_owned_by_service(self):
        result = self.run_aod(
            "wake", {"PROP_persist.sys.hibreak.aod_inverted": "1"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cmd settings put secure accessibility_display_inversion_enabled 0",
                      self.commands())
        self.assertIn("setprop persist.sys.hibreak.aod_inverted 0", self.commands())

    def test_setup_defaults_aod_once_and_clears_stale_inversion(self):
        result = self.run_aod(
            "setup", {
                "PROP_persist.sys.hibreak.aod_setup": "1",
                "PROP_persist.sys.hibreak.aod_inverted": "1",
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.commands()
        self.assertIn("cmd overlay enable me.phh.treble.overlay.misc.aod_systemui", commands)
        self.assertNotIn("cmd settings put secure doze_always_on 1", commands)
        self.assertIn("cmd settings put secure accessibility_display_inversion_enabled 0",
                      commands)

    def test_release_transform_uses_markers_not_exact_block_text(self):
        display = self.work / "display.rc"
        eink = self.work / "eink.rc"
        output = self.work / "out"
        display.write_text(
            "on boot\n"
            "# HIBREAK-RELEASE-REMOVE-BEGIN: disable-hwc-diagnostic\n"
            "# extra comment that should not break stripping\n"
            "on property:debug.hibreak.disable_hwc=1\n"
            "# HIBREAK-RELEASE-REMOVE-END: disable-hwc-diagnostic\n"
            "# HIBREAK-RELEASE-REMOVE-BEGIN: restart-surfaceflinger-diagnostic\n"
            "on property:debug.hibreak.restart_sf=1\n"
            "# HIBREAK-RELEASE-REMOVE-END: restart-surfaceflinger-diagnostic\n"
        )
        eink.write_text(
            "service a9_eink_server /system/bin/a9_eink_server\n"
            "# HIBREAK-RELEASE-REMOVE-BEGIN: eink-diagnostics\n"
            "on property:debug.hibreak.eink_restart=1\n"
            "# HIBREAK-RELEASE-REMOVE-END: eink-diagnostics\n"
        )
        subprocess.run(
            [sys.executable, RELEASE_SCRIPT, display, eink, output],
            check=True, capture_output=True, text=True,
        )
        self.assertEqual(
            (output / "hibreak-display-release.rc").read_text(),
            "on boot\n",
        )
        self.assertEqual(
            (output / "a9_eink_gsi-release.rc").read_text(),
            "service a9_eink_server /system/bin/a9_eink_server\n",
        )

    def test_release_transform_rejects_missing_marker(self):
        display = self.work / "display.rc"
        eink = self.work / "eink.rc"
        display.write_text("on boot\n")
        eink.write_text("")
        result = subprocess.run(
            [sys.executable, RELEASE_SCRIPT, display, eink, self.work / "out"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Expected exactly one release-removal block", result.stderr)


if __name__ == "__main__":
    unittest.main()
