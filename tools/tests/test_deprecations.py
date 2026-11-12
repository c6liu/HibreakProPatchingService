from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class DeprecationTests(unittest.TestCase):
    def test_positional_ir_binary_warns_before_input_validation(self):
        with tempfile.TemporaryDirectory(prefix="ir-deprecation-") as directory:
            output = Path(directory) / "output.img"
            result = subprocess.run(
                [
                    sys.executable, ROOT / "tools/image/add-ir-capture-to-gsi.py",
                    "missing.img", str(output), "capture", "--vendor-image", "vendor.img",
                ],
                capture_output=True, text=True,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Deprecated:", result.stderr)
        self.assertIn("--diagnostics-binary", result.stderr)
        self.assertIn("Missing dependency: secilc", result.stderr)


if __name__ == "__main__":
    unittest.main()
