import ctypes
import errno
import os
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


def nec_pattern(data=(0xea, 0xc7, 0x0f, 0xf0)):
    pattern = [9000, 4500]
    for byte in data:
        for bit in range(8):
            pattern.extend([560, 1690 if byte & (1 << bit) else 560])
    return pattern + [560]


class HxdNecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("cc")
        if not compiler:
            raise unittest.SkipTest("Missing C compiler")
        cls.work = tempfile.TemporaryDirectory(prefix="hxd-nec-test-")
        cls.addClassCleanup(cls.work.cleanup)
        library = Path(cls.work.name) / "nec.so"
        subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-fPIC", "-shared",
                        ROOT / "tools/ir/hxd-nec.c", "-o", library], check=True)
        cls.library = ctypes.CDLL(str(library))
        cls.encode = cls.library.hxd_nec_encode
        cls.encode.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.c_size_t,
                              ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ctypes.c_uint)]
        cls.encode.restype = ctypes.c_int

    def call(self, pattern, frequency=38000):
        array = (ctypes.c_int * len(pattern))(*pattern)
        output = (ctypes.c_ubyte * 10)(*[0xaa] * 10)
        duration = ctypes.c_uint(0xffffffff)
        result = self.encode(frequency, array, len(pattern), output, ctypes.byref(duration))
        return result, bytes(output), duration.value

    def test_confirmed_tcl_packet_and_optional_idle_gap(self):
        for gap in ([], [40000]):
            pattern = nec_pattern() + gap
            result, packet, duration = self.call(pattern)
            self.assertEqual(result, 0)
            self.assertEqual(packet, bytes.fromhex("30 00 01 0f f0 ea c7 00 00 e1"))
            self.assertEqual(duration, sum(pattern))

    def test_ir_blaster_nec_carrier_alias_and_exact_power_waveform(self):
        # NecProtocolEncoder emits stored MSB-first hex, 562/1687 timing, 108800 us.
        for code, expected in (
            ("57E3F00F", "30 00 01 0f f0 ea c7 00 00 e1"),
            ("57E3E916", "30 00 01 97 68 ea c7 00 00 e1"),
        ):
            pattern = [9000, 4500]
            for bit in f"{int(code, 16):032b}":
                pattern.extend([562, 1687 if bit == "1" else 562])
            pattern.append(562)
            pattern.append(108800 - sum(pattern))
            for frequency in (38000, 38222):
                result, packet, duration = self.call(pattern, frequency)
                self.assertEqual(result, 0)
                self.assertEqual(packet, bytes.fromhex(expected))
                self.assertEqual(duration, 108800)
        for frequency in (37999, 38001, 38200, 38221, 38223, 38400):
            self.assertEqual(self.call(nec_pattern(), frequency)[0], -errno.ENOTSUP)

    def test_nec_and_extended_all_byte_orders_and_checksums(self):
        generator = random.Random(123)
        for _ in range(256):
            address, extended, key = [generator.randrange(256) for _ in range(3)]
            for high in (address ^ 255, extended):
                result, packet, _ = self.call(nec_pattern((address, high, key, key ^ 255)))
                self.assertEqual(result, 0)
                self.assertEqual(packet[3:9], bytes([key, key ^ 255, address, high, 0, 0]))
                self.assertEqual(packet[-1], sum(packet[:-1]) & 255)

    def test_timing_tolerance_boundaries(self):
        pattern = nec_pattern()
        for index in range(len(pattern)):
            for percent in (85, 115):
                candidate = pattern.copy()
                candidate[index] = pattern[index] * percent // 100
                self.assertEqual(self.call(candidate)[0], 0, (index, percent))
            for value in (pattern[index] * 85 // 100 - 1, pattern[index] * 115 // 100 + 1):
                candidate = pattern.copy()
                candidate[index] = value
                self.assertLess(self.call(candidate)[0], 0, (index, value))

    def test_unsupported_is_atomic_and_does_not_mutate_outputs(self):
        good = nec_pattern()
        cases = [
            (good, 36000), (good, 40000), (good, 0),
            ([], 38000), (good[:-1], 38000), (good + [40000] + good, 38000),
            ([9000, 2250, 560], 38000), (good + [9999], 38000),
            (nec_pattern((0xea, 0xc7, 0x0f, 0x00)), 38000),
            ([0] + good[1:], 38000), ([-1] + good[1:], 38000),
            ([2147483647] + good[1:], 38000), (good + [2000000], 38000),
        ]
        for pattern, frequency in cases:
            result, output, duration = self.call(pattern, frequency)
            self.assertLess(result, 0)
            self.assertEqual(output, b"\xaa" * 10)
            self.assertEqual(duration, 0xffffffff)

    def test_two_second_limit_and_nulls(self):
        pattern = nec_pattern()
        result, _, duration = self.call(pattern + [2000000 - sum(pattern)])
        self.assertEqual(result, 0)
        self.assertEqual(duration, 2000000)
        self.assertEqual(self.call(pattern + [2000001 - sum(pattern)])[0], -errno.EINVAL)
        self.assertEqual(self.encode(38000, None, 67, None, None), -errno.EINVAL)

    def test_hal_abi_and_transport_with_mocked_controller(self):
        headers = Path(os.environ.get("AOSP_HEADERS", ROOT / "local/ir-hal-headers"))
        if not (headers / "hardware/consumerir.h").is_file():
            self.skipTest("Set AOSP_HEADERS to the Android 12 public HAL headers")
        binary = Path(self.work.name) / "mock-hal"
        subprocess.run(
            ["cc", "-std=c11", "-D_DEFAULT_SOURCE", "-Wall", "-Wextra", "-Werror",
             "-I", ROOT / "tools/tests/native/include", "-I", headers,
             ROOT / "tools/tests/native/hxd_hal_mock.c", ROOT / "tools/ir/hxd-nec.c",
             "-pthread", "-o", binary], check=True,
        )
        subprocess.run([binary], check=True, timeout=5)


if __name__ == "__main__":
    unittest.main()
