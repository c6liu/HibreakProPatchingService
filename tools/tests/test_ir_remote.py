from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]


class IrRemoteTests(unittest.TestCase):
    def test_native_request_and_status_without_hardware(self):
        compiler = shutil.which("cc")
        if not compiler:
            self.skipTest("Missing host C compiler")
        with tempfile.TemporaryDirectory(prefix="ir-remote-test-") as directory:
            binary = Path(directory) / "mock-remote"
            subprocess.run(
                [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                 "-I", ROOT / "tools/tests/native/include",
                 ROOT / "tools/tests/native/ir_remote_mock.c", "-o", binary],
                check=True,
            )
            subprocess.run([binary], check=True, timeout=5)

    def test_app_has_no_android_permissions_and_only_explicit_send(self):
        source = ROOT / "tools/ir/remote"
        manifest = ET.parse(source / "AndroidManifest.xml").getroot()
        self.assertEqual(manifest.attrib["package"], "com.hibreak.irremote")
        self.assertEqual(manifest.findall("uses-permission"), [])
        smali = (source / "smali/com/hibreak/irremote/MainActivity.smali").read_text()
        create = smali.split(".method public onCreate", 1)[1].split(".end method", 1)[0]
        self.assertNotIn("->request()", create)
        self.assertIn("->isPending()Z", create)
        self.assertIn("->run()V", create)
        self.assertEqual(smali.count("->request()Ljava/lang/String;"), 1)
        self.assertIn("->setEnabled(Z)V", smali)
        self.assertIn("->removeCallbacks(Ljava/lang/Runnable;)V", smali)
        rc = (ROOT / "tools/ir/hibreak-ir-remote.rc").read_text()
        self.assertIn("disabled\n    oneshot\n    timeout_period 10", rc)
        self.assertNotIn("on boot", rc)
        self.assertNotIn("sys.boot_completed", rc)
        policy = (ROOT / "tools/ir/hibreak-ir-remote.cil").read_text()
        self.assertNotIn("ctrl_device", policy)
        self.assertNotIn("debug_prop", policy)
        self.assertNotIn("(allow appdomain ", policy)
        contexts = (ROOT / "tools/ir/hibreak-ir-remote-seapp-contexts").read_text()
        self.assertIn("isPrivApp=true name=com.hibreak.irremote", contexts)

    def test_dedicated_app_domain_has_android_runtime_memory_rules(self):
        policy = (ROOT / "tools/ir/hibreak-ir-remote.cil").read_text()
        self.assertIn("(typeattributeset appdomain (hibreak_ir_remote))", policy)
        self.assertIn("(typetransition hibreak_ir_remote tmpfs file appdomain_tmpfs)", policy)
        self.assertIn(
            "(allow hibreak_ir_remote appdomain_tmpfs "
            "(file (ioctl read write getattr relabelfrom map execute)))", policy,
        )
        self.assertIn(
            '(typetransition hibreak_ir_remote hibreak_ir_remote anon_inode '
            '"[userfaultfd]" hibreak_ir_remote_userfaultfd)', policy,
        )
        self.assertIn(
            "(allow hibreak_ir_remote hibreak_ir_remote_userfaultfd "
            "(anon_inode (ioctl read create)))", policy,
        )
        self.assertNotIn("(allow hibreak_ir_remote tmpfs (file", policy)

    def test_dedicated_app_domain_can_start_activity_and_load_native_library(self):
        policy = (ROOT / "tools/ir/hibreak-ir-remote.cil").read_text()
        self.assertIn(
            "(allow hibreak_ir_remote app_api_service (service_manager (find)))", policy,
        )
        self.assertIn("(allow hibreak_ir_remote privapp_data_file (file (execute)))", policy)
        self.assertIn(
            "(allow hibreak_ir_remote system_linker_exec (file (execute_no_trans)))", policy,
        )
        self.assertNotIn("(allow hibreak_ir_remote service_manager_type", policy)
        self.assertNotIn("(allow priv_app hibreak_ir_request_prop", policy)

    def test_api_client_uses_only_standard_permission_and_correct_nec_bytes(self):
        source = ROOT / "tools/ir/api-test"
        manifest = ET.parse(source / "AndroidManifest.xml").getroot()
        android_name = "{http://schemas.android.com/apk/res/android}name"
        self.assertEqual(manifest.attrib["package"], "com.hibreak.irapitest")
        self.assertEqual([p.attrib[android_name] for p in manifest.findall("uses-permission")],
                         ["android.permission.TRANSMIT_IR"])
        smali = (source / "smali/com/hibreak/irapitest/MainActivity.smali").read_text()
        self.assertIn("Landroid/hardware/ConsumerIrManager;->transmit(I[I)V", smali)
        self.assertNotIn("->loadLibrary", smali)
        self.assertNotIn("setprop", smali)
        create = smali.split(".method public onCreate", 1)[1].split(".end method", 1)[0]
        self.assertNotIn("->transmit", create)
        import re
        word = int(re.search(r"const v1, (-0x[0-9a-f]+)", smali).group(1), 16) & 0xffffffff
        self.assertEqual(word.to_bytes(4, "little"), bytes.fromhex("ea c7 0f f0"))


if __name__ == "__main__":
    unittest.main()
