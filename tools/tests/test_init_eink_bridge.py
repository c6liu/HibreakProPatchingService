import importlib.util
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("init_eink_bridge", ROOT / "tools/add-eink-init-bridge-to-gsi.py")
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


class InitEinkBridgeTests(unittest.TestCase):
    def test_exact_typed_request_properties(self):
        baseline = "sys. u:object_r:system_prop:s0\n"
        result = bridge.add_contexts(baseline, [])
        for request in bridge.REQUESTS:
            self.assertIn(f"{request} {bridge.LABEL} exact enum 0 1\n", result)
            with self.assertRaisesRegex(ValueError, "already has an exact"):
                bridge.add_contexts(baseline + f"{request} u:object_r:system_prop:s0 exact string\n", [])

    def test_init_actions_are_fixed_values_and_paths(self):
        text = (ROOT / "tools/display/hibreak-init-eink-bridge.rc").read_text()
        actions = re.findall(r"^on property:(\S+)=(\S+)\n    write (\S+) (\S+)$", text, re.M)
        expected = {
            (request, value, "/sys/kernel/debug" + node, value)
            for request, node in zip(bridge.REQUESTS, bridge.NODES)
            for value in ("0", "1")
        }
        self.assertEqual(len(actions), 4)
        self.assertEqual(set(actions), expected)

    def test_cil_grants_only_init_hardware_write(self):
        cil = (ROOT / "tools/display/hibreak-init-eink-bridge.cil").read_text()
        self.assertIn("(allow init hibreak_eink_bridge_debugfs (file (open write)))", cil)
        self.assertNotIn("(allow phhsu_daemon hibreak_eink_bridge_debugfs", cil)
        self.assertNotIn("(typepermissive", cil)
        for node in bridge.NODES:
            self.assertIn(f'(genfscon debugfs "{node}"', cil)


if __name__ == "__main__":
    unittest.main()
