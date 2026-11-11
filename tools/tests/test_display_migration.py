import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "display_migration", ROOT / "tools/add-display-migration-to-gsi.py",
)
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)


class DisplayMigrationTests(unittest.TestCase):
    def test_init_changes_only_five_service_labels(self):
        source = (ROOT / "tools/display/hibreak-display.rc").read_text()
        result = migration.migrate_init(source)
        self.assertEqual(result.count("seclabel u:r:hibreak_display:s0"), 5)
        self.assertEqual(result.replace("seclabel u:r:hibreak_display:s0",
                                        "seclabel u:r:phhsu_daemon:s0"), source)
        with self.assertRaises(ValueError):
            migration.migrate_init(source.replace("seclabel u:r:phhsu_daemon:s0", "", 1))

    def test_contexts_are_exact_and_do_not_override_legacy(self):
        source = "persist.sys. u:object_r:system_prop:s0\n"
        result = migration.add_contexts(source, [])
        for name in migration.STATE_NAMES:
            self.assertIn(f"{name} {migration.STATE_LABEL} exact enum 0 1\n", result)
            with self.assertRaises(ValueError):
                migration.add_contexts(source + f"{name} u:object_r:system_prop:s0 exact string\n", [])

    def test_state_migration_and_aod_cycles(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            bin_dir = work / "bin"
            bin_dir.mkdir()
            state = work / "state.json"
            events = work / "events"
            stub = bin_dir / "stub"
            stub.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, pathlib, sys\n"
                "name = pathlib.Path(sys.argv[0]).name\n"
                "args = sys.argv[1:]\n"
                "path = pathlib.Path(os.environ['STATE'])\n"
                "state = json.loads(path.read_text())\n"
                "with open(os.environ['EVENTS'], 'a') as f: f.write(name + ' ' + ' '.join(args) + '\\n')\n"
                "if name == 'setprop' and os.environ.get('FAIL_SETPROP') == '1': sys.exit(1)\n"
                "if name == 'getprop': print(state.get(args[0], ''))\n"
                "elif name == 'setprop':\n"
                "    state[args[0]] = args[1]; path.write_text(json.dumps(state))\n"
                "elif name == 'cmd' and args[:2] == ['settings', 'get']:\n"
                "    print(state.get('setting:' + args[-1], '0'))\n"
                "elif name == 'cmd' and args[:2] == ['settings', 'put']:\n"
                "    state['setting:' + args[-2]] = args[-1]; path.write_text(json.dumps(state))\n"
            )
            stub.chmod(0o755)
            for name in ("getprop", "setprop", "cmd", "log"):
                (bin_dir / name).symlink_to(stub)
            script = work / "aod.sh"
            script.write_text(migration.migrate_aod(
                (ROOT / "tools/display/hibreak-aod.sh").read_text()))
            env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}",
                       STATE=str(state), EVENTS=str(events))

            def run(action):
                result = subprocess.run(["sh", script, action], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)

            state.write_text(json.dumps({
                "persist.sys.hibreak.aod_setup": "1",
                "persist.sys.hibreak.aod_inverted": "1",
                "setting:accessibility_display_inversion_enabled": "1",
                "setting:doze_always_on": "1",
            }))
            run("setup")
            current = json.loads(state.read_text())
            self.assertEqual(current[migration.STATE_NAMES[0]], "0")
            self.assertEqual(current[migration.STATE_NAMES[1]], "1")
            self.assertEqual(current["setting:accessibility_display_inversion_enabled"], "0")
            self.assertNotIn("cmd settings put secure doze_always_on 1", events.read_text())
            run("doze")
            current = json.loads(state.read_text())
            self.assertEqual(current[migration.STATE_NAMES[0]], "1")
            self.assertEqual(current["setting:accessibility_display_inversion_enabled"], "1")
            run("wake")
            current = json.loads(state.read_text())
            self.assertEqual(current[migration.STATE_NAMES[0]], "0")
            self.assertEqual(current["setting:accessibility_display_inversion_enabled"], "0")
            run("wake")
            self.assertEqual(json.loads(state.read_text())[migration.STATE_NAMES[0]], "0")
            state.write_text(json.dumps({
                "persist.sys.hibreak.display.aod_inverted": "0",
                "persist.sys.hibreak.display.aod_setup": "1",
                "persist.sys.hibreak.aod_inverted": "1",
                "persist.sys.hibreak.aod_setup": "1",
                "persist.sys.hibreak.aod_invert": "false",
                "setting:doze_always_on": "1",
                "setting:accessibility_display_inversion_enabled": "0",
            }))
            run("doze")
            current = json.loads(state.read_text())
            self.assertEqual(current[migration.STATE_NAMES[0]], "0")
            self.assertEqual(current["setting:accessibility_display_inversion_enabled"], "0")
            state.write_text(json.dumps({
                "persist.sys.hibreak.aod_invert": "true",
                "setting:doze_always_on": "1",
                "setting:accessibility_display_inversion_enabled": "1",
            }))
            run("doze")
            self.assertNotIn(migration.STATE_NAMES[0], json.loads(state.read_text()))
            events.write_text("")
            state.write_text(json.dumps({
                "persist.sys.hibreak.aod_setup": "1",
                "persist.sys.hibreak.aod_inverted": "1",
            }))
            result = subprocess.run(["sh", script, "setup"],
                                    env=dict(env, FAIL_SETPROP="1"),
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("AOD operation failed", events.read_text())
            self.assertNotIn("cmd overlay enable", events.read_text())

    def test_unexpected_aod_source_is_rejected(self):
        with self.assertRaises(ValueError):
            migration.migrate_aod("MARK=persist.sys.hibreak.aod_inverted\n")


if __name__ == "__main__":
    unittest.main()
