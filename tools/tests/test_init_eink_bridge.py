from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
from tools.hibreak import eink_bridge as bridge


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

    def test_compiled_policy_checks_permissions_and_node_labels(self):
        baseline = {("system_server", "file", "read")}
        permissions = {
            "hibreak_eink_bridge_debugfs": baseline | {
                ("init", "file", "open"), ("init", "file", "write")},
            "hibreak_eink_bridge_prop": {
                ("init", "property_service", "set"),
                ("phhsu_daemon", "property_service", "set")},
        }
        nodes = [SimpleNamespace(fs="debugfs", path=node,
                                 context=SimpleNamespace(type_="hibreak_eink_bridge_debugfs"))
                 for node in bridge.NODES]
        policy = SimpleNamespace(genfscons=lambda: nodes)
        query = mock.Mock(return_value=SimpleNamespace(results=lambda: [object()]))
        modules = {"setools": SimpleNamespace(TERuleQuery=query),
                   "setools.exception": SimpleNamespace(RuleNotConditional=Exception)}
        with mock.patch.dict(sys.modules, modules), \
                mock.patch.object(bridge, "effective_permissions",
                                  side_effect=lambda _policy, target, *_args: permissions[target]):
            bridge.validate_bridge_policy(policy, baseline)
            permissions["hibreak_eink_bridge_prop"].add(("untrusted_app", "property_service", "set"))
            with self.assertRaisesRegex(ValueError, "Unexpected bridge property writers"):
                bridge.validate_bridge_policy(policy, baseline)
            permissions["hibreak_eink_bridge_prop"].remove(("untrusted_app", "property_service", "set"))
            nodes.pop()
            with self.assertRaisesRegex(ValueError, "Bridge node label missing"):
                bridge.validate_bridge_policy(policy, baseline)


if __name__ == "__main__":
    unittest.main()
