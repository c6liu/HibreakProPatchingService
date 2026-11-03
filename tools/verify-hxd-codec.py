#!/usr/bin/env python3
# /// script
# dependencies = ["unicorn==2.1.4"]
# ///
import argparse
import hashlib
import random
import struct
import zipfile
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_MODE_THUMB
from unicorn.arm_const import (
    UC_ARM_REG_LR,
    UC_ARM_REG_PC,
    UC_ARM_REG_R0,
    UC_ARM_REG_R1,
    UC_ARM_REG_R2,
    UC_ARM_REG_R5,
    UC_ARM_REG_R6,
    UC_ARM_REG_SP,
)

parser = argparse.ArgumentParser(
    description="Verify HxdIR codec rules by emulating isolated native routines; no device access"
)
parser.add_argument("apk", type=Path, help="Local HxdIR APK matching the documented library hash")
args = parser.parse_args()
if not __debug__:
    parser.error("Run without Python optimization: this verification harness requires assertions")

with zipfile.ZipFile(args.apk) as apk:
    image = apk.read("lib/armeabi/libet_jni_ir_tools.so")
if hashlib.sha256(image).hexdigest() != (
    "513b6dd35a2f0b8cef6d3906341587c4586a3178539150d7bd26552db1c2aceb"
):
    parser.error("Native library hash differs from the analyzed HxdIR build")


def virtual_bytes(address, size):
    phoff = struct.unpack_from("<I", image, 28)[0]
    phsize, phcount = struct.unpack_from("<HH", image, 42)
    for index in range(phcount):
        kind, offset, base, _, filesz, _, _, _ = struct.unpack_from(
            "<8I", image, phoff + index * phsize
        )
        if kind == 1 and base <= address and address + size <= base + filesz:
            start = offset + address - base
            return image[start:start + size]
    raise ValueError("Code range is not file-backed")


def execute(address, values, count):
    emulator = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    emulator.mem_map(0x5000, 0x2000)
    emulator.mem_write(0x52BC, virtual_bytes(0x52BC, 0x565C - 0x52BC))
    emulator.mem_map(0x100000, 0x1000)
    emulator.mem_map(0x200000, 0x10000)
    emulator.mem_map(0x300000, 0x1000)
    words = [0, 0, count, 0, 0] + values
    emulator.mem_write(0x100000, struct.pack("<" + "I" * len(words), *words))
    emulator.mem_write(0x100800, struct.pack("<I", len(words) - 1))
    emulator.reg_write(UC_ARM_REG_R0, 0x100000)
    emulator.reg_write(UC_ARM_REG_R1, 0x100800)
    emulator.reg_write(UC_ARM_REG_SP, 0x20FFF0)
    emulator.reg_write(UC_ARM_REG_LR, 0x300001)
    emulator.emu_start(address | 1, 0x300000, count=10000)
    assert emulator.reg_read(UC_ARM_REG_PC) == 0x300000, "Routine did not return within instruction limit"
    result = emulator.reg_read(UC_ARM_REG_R0)
    output = struct.unpack("<16I", emulator.mem_read(0x100000, 64))
    return result, list(output[5:])


cases = [
    ("M708 cumulative pair", 0x5508, [0x80, 160, 0x82, 128], 2, 0, [7, 31]),
    ("M708 minimum space", 0x5508, [16, 16], 2, 0, [1, 4]),
    ("M708 extended marker", 0x5508, [0xF0, 0, 160, 0x82, 128], 2, 0, [7, 31]),
    ("M708 extended space", 0x5508, [0x80, 160, 0xF1, 0, 0], 2, 0, [7, 0x8F, 248]),
    ("M708 127 boundary", 0x5508, [0x87, 253, 0x8A, 0], 2, 0, [124, 34]),
    ("M708 128 boundary", 0x5508, [0x87, 254, 0x8A, 0], 2, 0, [0x80, 123, 33]),
    ("M708 largest accepted even value", 0x5508, [0x88, 13, 0x8A, 0], 2, 0, [0x80, 123, 33]),
    ("M708 129 rejection", 0x5508, [0x88, 14, 0x8A, 0], 2, 1, []),
    ("M708 4093 boundary rejection", 0x5508, [0x8F, 253, 0x92, 192], 2, 1, []),
    ("M708 4094 boundary rejection", 0x5508, [0x8F, 254, 0x92, 192], 2, 1, []),
    ("M708 oversized even value", 0x5508, [0x88, 32], 1, 1, []),
    ("Modifywave alternating adjustment", 0x52BC, [20, 30, 40, 50], 4, 0, [15, 33, 33, 53]),
    ("Modifywave minimum mark", 0x52BC, [7, 1], 2, 0, [4, 4]),
    ("delfeng observed short odd interval rewrite", 0x53D8, [20, 3, 30, 40], 4, None, [26, 3, 30, 40]),
]
for name, address, values, count, expected_status, expected in cases:
    status, output = execute(address, values, count)
    if expected_status is not None:
        assert status == expected_status, (name, status, expected_status)
    assert output[:len(expected)] == expected, (name, output, expected)
    status_text = status if expected_status is not None else "not asserted"
    print(f"PASS: {name}: status={status_text}, prefix={output[:len(expected)]}")


def extended_packet(record, padding=bytes(7)):
    emulator = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    emulator.mem_map(0x2000, 0x1000)
    emulator.mem_write(0x29E8, virtual_bytes(0x29E8, 0x2BF0 - 0x29E8))
    emulator.mem_map(0x100000, 0x1000)
    emulator.mem_map(0x200000, 0x1000)
    emulator.mem_write(0x100000, bytes(record) + padding)
    stack = 0x200100
    emulator.mem_write(stack + 0x18, struct.pack("<i", -37))
    emulator.reg_write(UC_ARM_REG_R6, 0x100000)
    emulator.reg_write(UC_ARM_REG_R1, 36)
    emulator.reg_write(UC_ARM_REG_SP, stack)
    reads = []

    def record_read(uc, access, address, size, value, user_data):
        if 0x100000 <= address < 0x101000:
            reads.append(address - 0x100000)

    emulator.hook_add(UC_HOOK_MEM_READ, record_read)
    emulator.emu_start(0x2A25, 0x2B70, count=20000)
    assert reads and max(reads) < 230, "Extended conversion read beyond its input"
    assert emulator.reg_read(UC_ARM_REG_PC) == 0x2B70, (
        "Extended conversion did not finish", hex(emulator.reg_read(UC_ARM_REG_PC))
    )
    assert emulator.reg_read(UC_ARM_REG_R0) == 232
    return bytes(emulator.mem_read(stack + 0x20, 232))


def expected_extended_packet(record, padding=bytes(7)):
    record = bytearray(record) + padding
    for index in range(37, 227):
        if record[index] & 8:
            record[index] |= 15
        elif record[index] & 128:
            record[index] = 240
    for base in range(178):
        if not any(record[base + 38:base + 47]):
            if not record[base + 37] & 15:
                record[base + 37] |= 15
            record[base + 38] = 255
            break
    for index in range(37, 227):
        if record[index] & 8:
            record[index] |= 15
        if record[index] & 128:
            record[index] = 255
    if 33 <= record[8] < 128:
        record[8] = 1
        record[7] = 21
    if record[2] <= 3 or record[2] >= 128:
        record[2] = 254
    if record[1] <= 4 or record[1] >= 128:
        record[1] = 254
    if record[4] == 0:
        record[4] = 52
    packet = bytes([0x30, 0x03]) + record[1:230]
    return packet + bytes([sum(packet) & 255])


extended_cases = [
    ("all-zero synthetic record", bytes(230), bytes(7)),
    ("bit masks and nonzero field 4", bytes(range(230)), bytes(7)),
    ("signed-byte header handling", bytes([255]) * 230, bytes(7)),
    ("preserved positive headers", bytes([16]) * 230, bytes(7)),
    ("zero tail with zero adjacent memory", bytes([16]) * 228 + bytes(2), bytes(7)),
    ("zero tail with nonzero adjacent memory", bytes([16]) * 228 + bytes(2), bytes([16]) * 7),
]
rng = random.Random(0)
extended_cases.extend(
    (f"deterministic synthetic record {index}", rng.randbytes(230), bytes(7))
    for index in range(16)
)
for name, record, padding in extended_cases:
    packet = extended_packet(record, padding)
    expected = expected_extended_packet(record, padding)
    assert packet == expected, (name, packet.hex(), expected.hex())
    assert packet[:2] == b"\x30\x03" and len(packet) == 232
    assert packet[-1] == sum(packet[:-1]) & 255
    print(f"PASS: extended {name}: exact 232-byte packet and checksum")
tail_record = bytes([16]) * 228 + bytes(2)
assert extended_packet(tail_record) == extended_packet(tail_record, bytes([16]) * 7)
print("PASS: extended tail output is independent of controlled adjacent memory")
no_signal = b"\x00\x88\x99\xaa\x00" + b"\xff" * 32 + bytes(190) + b"\xf2\xe1\x51"
assert len(no_signal) == 230
assert hashlib.sha256(no_signal).hexdigest() == "1adcddd588b95e03b2f2200326c1e6f8ab97e7aeb4750628e8e793666d88b38c"
no_signal_packet = extended_packet(no_signal)
assert no_signal_packet == expected_extended_packet(no_signal)
assert no_signal_packet[2:6] == b"\xfe\xfe\xaa\x34"
print("PASS: observed no-signal record also converts to 232 bytes; conversion is NOT learning validation")
for field in range(256):
    record = bytearray([16] * 230)
    record[0] = 0
    record[4] = field
    packet = extended_packet(record)
    assert packet == expected_extended_packet(record)
    assert packet[5] == (field or 52), (field, packet[5])
print("PASS: all 256 extended field-4 values: zero defaults to 52, all nonzero values pass through")


def compact_database_packet(fields):
    emulator = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    emulator.mem_map(0x3000, 0x1000)
    emulator.mem_write(0x3800, virtual_bytes(0x3800, 0x3830 - 0x3800))
    emulator.mem_map(0x100000, 0x1000)
    emulator.mem_map(0x200000, 0x1000)
    emulator.mem_write(0x100000, fields)
    emulator.mem_write(0x100100, b"\x30\x00" + fields[:1])
    emulator.mem_write(0x200128, struct.pack("<I", fields[0]))
    emulator.reg_write(UC_ARM_REG_R0, 0x100100)
    emulator.reg_write(UC_ARM_REG_R1, 0x100000)
    emulator.reg_write(UC_ARM_REG_SP, 0x200100)
    emulator.emu_start(0x3801, 0x3830, count=1000)
    assert emulator.reg_read(UC_ARM_REG_PC) == 0x3830, "Compact packet assembly did not finish"
    return bytes(emulator.mem_read(0x100100, 10))


compact_cases = [bytes(7), bytes(range(7)), bytes([255]) * 7, bytes([16]) * 7]
for index, fields in enumerate(compact_cases):
    packet = compact_database_packet(fields)
    expected = b"\x30\x00" + fields
    expected += bytes([sum(expected) & 255])
    assert packet == expected, (index, packet.hex(), expected.hex())
    print(f"PASS: compact database synthetic fields {index}: exact 10-byte packet and checksum")


def identifier_database_packet(identifier, selector, data):
    emulator = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    emulator.mem_map(0x2000, 0x2000)
    emulator.mem_write(0x3C40, virtual_bytes(0x3C40, 0x3CA2 - 0x3C40))
    emulator.mem_map(0x100000, 0x1000)
    emulator.mem_map(0x200000, 0x1000)
    emulator.mem_write(0x100000, bytes([len(data)]) + data)
    stack = 0x200100
    emulator.mem_write(stack + 0x14, struct.pack("<I", selector))
    emulator.mem_write(stack + 0x28, struct.pack("<I", 0x100000))
    emulator.reg_write(UC_ARM_REG_SP, stack)
    emulator.reg_write(UC_ARM_REG_R0, 255)
    emulator.reg_write(UC_ARM_REG_R1, 0x100000)
    emulator.reg_write(UC_ARM_REG_R2, 1)
    emulator.reg_write(UC_ARM_REG_R5, identifier)

    def copy_data(uc, address, size, user_data):
        if address != 0x2288:
            return
        destination = uc.reg_read(UC_ARM_REG_R0)
        source = uc.reg_read(UC_ARM_REG_R1)
        length = uc.reg_read(UC_ARM_REG_R2)
        assert destination == stack + 0x40 and source == 0x100001
        assert length == len(data), "Unexpected memcpy arguments"
        uc.mem_write(destination, bytes(uc.mem_read(source, length)))
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    emulator.hook_add(UC_HOOK_CODE, copy_data)
    emulator.emu_start(0x3C41, 0x3CA2, count=10000)
    assert emulator.reg_read(UC_ARM_REG_PC) == 0x3CA2, "Identifier packet assembly did not finish"
    length = struct.unpack("<I", emulator.mem_read(stack + 0x20, 4))[0]
    assert length == len(data) + 18
    return bytes(emulator.mem_read(stack + 0x30, length))


identifier_cases = [
    (0xC001, 160, b""),
    (0xC001, 160, b"\x12"),
    (0xC023, 160, b"\x00\xff\x34"),
    (0xC001, 160, bytes(range(38))),
    (0xC001, 160, bytes(range(255))),
]
for identifier, selector, data in identifier_cases:
    packet = identifier_database_packet(identifier, selector, data)
    expected = (
        b"\x30\x01" + identifier.to_bytes(2, "big") + bytes(11)
        + bytes([(len(data) + 1) & 255]) + data
        + bytes([(selector + 95) & 255])
    )
    repeated_byte = data[-1] if data else 1
    checksum = 0x31 + (identifier >> 8) + (identifier & 255)
    checksum += ((len(data) + 1) & 255) + sum(data) + repeated_byte
    expected += bytes([checksum & 255])
    assert packet == expected, (identifier, selector, len(data), packet.hex(), expected.hex())
    print(f"PASS: identifier database packet: {len(data)} data bytes, exact native layout/checksum")
checksum_probe = identifier_database_packet(0xC001, 160, b"\x12")
assert checksum_probe[-2] == 255
assert checksum_probe[-1] != sum(checksum_probe[:-1]) & 255
print("PASS: identifier native checksum is not the ordinary sum of preceding packet bytes")


class ShortRecordEmulator:
    def __init__(self):
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        phoff = struct.unpack_from("<I", image, 28)[0]
        phsize, phcount = struct.unpack_from("<HH", image, 42)
        for index in range(phcount):
            kind, offset, base, _, filesz, memsz, _, _ = struct.unpack_from(
                "<8I", image, phoff + index * phsize
            )
            if kind == 1:
                page = base & ~4095
                size = (base + memsz + 4095) & ~4095
                self.uc.mem_map(page, size - page)
                self.uc.mem_write(base, image[offset:offset + filesz])
        self.uc.mem_map(0x10000000, 0x10000)
        self.uc.mem_map(0x20000000, 0x10000)
        self.uc.mem_map(0x30000000, 0x1000)
        shoff = struct.unpack_from("<I", image, 32)[0]
        shsize, shcount = struct.unpack_from("<HH", image, 46)
        sections = [
            struct.unpack_from("<10I", image, shoff + index * shsize)
            for index in range(shcount)
        ]
        self.symbols = {}
        self.plt = {}
        for section in sections:
            if section[1] != 9:
                continue
            symtab = sections[section[6]]
            strings = sections[symtab[6]]
            for offset in range(section[4], section[4] + section[5], section[9]):
                address, info = struct.unpack_from("<II", image, offset)
                symoff = symtab[4] + (info >> 8) * symtab[9]
                nameoff, value, _, _, _, defined = struct.unpack_from("<IIIBBH", image, symoff)
                start = strings[4] + nameoff
                name = image[start:image.index(b"\0", start)].decode()
                if defined:
                    self.symbols[name] = value
                relocation = info & 255
                if relocation in (21, 22) and defined:
                    self.uc.mem_write(address, struct.pack("<I", value))
                if name == "__stack_chk_guard":
                    self.uc.mem_write(address, struct.pack("<I", 0x1000F000))
                if relocation == 22:
                    self.plt[0x2264 + len(self.plt) * 12] = (name, value, defined)
        self.calls = []
        self.uc.hook_add(UC_HOOK_CODE, self.external_call, begin=0x2250, end=0x2600)

    def external_call(self, uc, address, size, user_data):
        if address not in self.plt:
            raise RuntimeError(f"Unexpected PLT instruction: {address:#x}")
        name, value, defined = self.plt[address]
        self.calls.append(name)
        if defined and (0x3E78 <= value < 0x596C or name in ("__aeabi_idiv", "__aeabi_idivmod")):
            uc.reg_write(UC_ARM_REG_PC, value)
            return
        destination = uc.reg_read(UC_ARM_REG_R0)
        if name in ("__aeabi_memcpy", "memcpy"):
            source = uc.reg_read(UC_ARM_REG_R1)
            length = uc.reg_read(UC_ARM_REG_R2)
            assert length <= 112, (name, length)
            uc.mem_write(destination, bytes(uc.mem_read(source, length)))
        elif name in ("__aeabi_memclr", "__aeabi_memclr4"):
            length = uc.reg_read(UC_ARM_REG_R1)
            assert length <= 112, (name, length)
            uc.mem_write(destination, bytes(length))
        elif name == "__android_log_print":
            uc.reg_write(UC_ARM_REG_R0, 0)
        else:
            raise RuntimeError(f"Disallowed external call: {name}")
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    def call(self, address, arg0, arg1=0):
        self.uc.reg_write(UC_ARM_REG_SP, 0x2000FFF0)
        self.uc.reg_write(UC_ARM_REG_R0, arg0)
        self.uc.reg_write(UC_ARM_REG_R1, arg1)
        self.uc.reg_write(UC_ARM_REG_LR, 0x30000001)
        self.uc.emu_start(address | 1, 0x30000000, count=200000)
        assert self.uc.reg_read(UC_ARM_REG_PC) == 0x30000000, "Short-record instruction limit exceeded"
        return self.uc.reg_read(UC_ARM_REG_R0)


short = ShortRecordEmulator()
segment_a = [10, 20, 10, 30, 10, 20, 10, 100]
segment_b = [50, 60, 50, 60, 50, 60, 50, 100]
segment_cases = [
    ("single A", segment_a, 1, 8, 8),
    ("A+A", segment_a * 2, 1, 8, 8),
    ("A+A+A", segment_a * 3, 1, 8, 8),
    ("A+B+A", segment_a + segment_b + segment_a, 3, 8, 16),
    ("A+B+B", segment_a + segment_b * 2, 2, 8, 16),
    ("long+short+short", [10, 20, 10, 30, 10, 100, 10, 100, 10, 100], 2, 6, 8),
]
for flags in (0, 0x40, 0x80, 0x88):
    for name, stream, classification, first_boundary, second_boundary in segment_cases:
        words = [0, flags, len(stream), 0, 52] + stream
        short.uc.mem_write(0x10000000, struct.pack("<" + "I" * len(words), *words))
        short.uc.mem_write(0x10000800, struct.pack("<I", len(words)))
        assert short.call(0x565C, 0x10000000, 0x10000800) == 0
        header = struct.unpack("<5I", short.uc.mem_read(0x10000000, 20))
        if flags == 0x40:
            expected = (0, 0, len(stream), len(stream), 52)
        else:
            expected = (0, flags | classification, first_boundary, second_boundary, 52)
        assert header == expected, (name, flags, header, expected)
print("PASS: 24 segment-classifier vectors: counts/boundaries, not number of host resends")

short_inputs = [
    (
        bytes([0, 0, 2, 0, 52, 0x80, 160, 0x82, 128]) + bytes(101),
        bytes([1, 2, 2, 52, 7, 31, 130, 128]) + bytes(102),
    ),
    (
        bytes([0, 128, 4, 0, 52, 20, 30, 40, 50]) + bytes(101),
        bytes([129, 4, 4, 52, 15, 33, 33, 53]) + bytes(102),
    ),
]
for index, (record, expected_normalized) in enumerate(short_inputs):
    short.uc.mem_write(short.symbols["g_toggle_bit"], b"\0")
    short.uc.mem_write(0x10000000, record)
    status = short.call(0x3F98, 0x10000000)
    normalized = bytes(short.uc.mem_read(0x10000000, 110))
    assert status == 109 and normalized == expected_normalized, (index, status, normalized.hex())
    for repeat in range(3):
        status = short.call(0x400C, 0x10000000, 109)
        packet = bytes(short.uc.mem_read(short.symbols["g_i2c_cmd_buffer"], 112))
        payload = bytearray(expected_normalized[:109])
        payload[0] ^= 0x10 if repeat % 2 else 0
        expected = b"\x30\x02" + payload
        expected += bytes([sum(expected) & 255])
        assert status == 109 and packet == expected, (index, repeat, packet.hex())
    print(f"PASS: complete short record {index}: normalization, metadata, three stateful packets")

for field in range(256):
    record = bytearray(short_inputs[0][0])
    record[4] = field
    short.uc.mem_write(0x10000000, bytes(record))
    assert short.call(0x3F98, 0x10000000) == 109
    assert short.uc.mem_read(0x10000003, 1) == bytes([field])
    assert short.call(0x400C, 0x10000000, 109) == 109
    assert short.uc.mem_read(short.symbols["g_i2c_cmd_buffer"] + 5, 1) == bytes([field])
print("PASS: all 256 candidate carrier values pass unchanged through complete short-record helpers")

for record in (
    bytes([1]) + short_inputs[0][0][1:],
    bytes([0, 0, 1, 0, 52, 0x88, 14]) + bytes(103),
):
    short.uc.mem_write(0x10000000, record)
    assert short.call(0x3F98, 0x10000000) == 0
    assert bytes(short.uc.mem_read(0x10000000, 110)) == record
print("PASS: short-record rejection returns zero and leaves caller input unchanged")

short.uc.mem_write(0x10000000, bytes(112))
assert short.call(0x3E78, 0x10000000) == 0
assert bytes(short.uc.mem_read(0x10000000, 112)) == bytes(112)
print("PASS: learned wrapper rejects zero byte 1 before normalization")
wrapper_record = bytes([0, 128, 8, 0, 52, 32, 30, 32, 40, 32, 50, 32, 100]) + bytes(99)
short.uc.mem_write(short.symbols["g_toggle_bit"], b"\0")
short.uc.mem_write(0x10000000, wrapper_record)
assert short.call(0x3E78, 0x10000000) == 0
wrapper_packet = bytes(short.uc.mem_read(0x10000000, 112))
wrapper_expected = bytes([0x30, 2, 0x81, 8, 8, 52, 27, 33, 25, 43, 25, 53, 25, 103]) + bytes(97)
wrapper_expected += bytes([sum(wrapper_expected) & 255])
assert wrapper_packet == wrapper_expected
print("PASS: complete learned wrapper: exact accepted 112-byte packet")


def packed_values(values):
    packed = []
    for value in values:
        assert 0 <= value <= 32767
        if value < 128:
            packed.append(value)
        else:
            packed.extend([128 | (value >> 8), value & 255])
    return packed


def rc5_durations():
    bits = [1, 1, 0] + [0] * 11
    levels = [level for bit in bits for level in ([0, 1] if bit else [1, 0])]
    while levels and not levels[0]:
        levels.pop(0)
    if levels and not levels[-1]:
        levels.pop()
    durations = []
    previous = None
    for level in levels:
        if level == previous:
            durations[-1] += 889
        else:
            durations.append(889)
        previous = level
    return durations


nec_durations = [9000, 4500]
for value in (0, 255, 0, 255):
    for bit in range(8):
        nec_durations.extend([560, 1690 if value & (1 << bit) else 565])
nec_durations.append(560)
protocol_checks = 0
for name, durations in (("RC5", rc5_durations()), ("NEC", nec_durations)):
    for unit in (1, 2, 4, 8, 14, 16, 18, 20, 22, 32, 64):
        values = [round(duration / unit) for duration in durations]
        words = [0, 1, len(values), 0, 52] + packed_values(values)
        short.uc.mem_write(0x10000000, bytes(2048))
        short.uc.mem_write(0x10000000, struct.pack("<" + "I" * len(words), *words))
        classification = short.call(0x416C, 0x10000000)
        expected = 2 if name == "RC5" and unit in (16, 18) else 0
        assert classification == expected, (name, unit, classification, expected)
        protocol_checks += 1
        print(f"PASS: synthetic {name}, hypothesized {unit} us/unit: toggle classification {classification}")
print("PASS: RC5 matches two time scales; the classifier does not uniquely calibrate the clock")
rc5_values = [round(duration / 16) for duration in rc5_durations()]
rc5_payload = bytes([1, len(rc5_values), len(rc5_values), 52] + packed_values(rc5_values))
rc5_payload += bytes(109 - len(rc5_payload))
short.uc.mem_write(0x10000000, rc5_payload)
short.uc.mem_write(short.symbols["g_toggle_bit"], b"\0")
rc5_packets = []
for _ in range(3):
    assert short.call(0x400C, 0x10000000, 109) == 109
    packet = bytes(short.uc.mem_read(short.symbols["g_i2c_cmd_buffer"], 112))
    assert packet[:2] == b"\x30\x02"
    assert packet[-1] == sum(packet[:-1]) & 255
    rc5_packets.append(packet)
assert rc5_packets[0] == rc5_packets[2]
assert rc5_packets[0][6:-1] != rc5_packets[1][6:-1], "Expected waveform-level RC5 toggle modification"
print("PASS: synthetic RC5 replay changes waveform bytes on alternate sends, not only a header flag")
print(
    f"Verified {len(cases)} native routine vectors, {len(extended_cases) + 1} fixed extended packets, "
    f"{len(compact_cases)} compact database packets, and {len(identifier_cases)} identifier packets; "
    "plus 256 extended and 256 short carrier-field probes, 24 segment classifiers, "
    f"complete short-record checks and {protocol_checks} protocol hypotheses. "
    "No JNI callbacks, transport, or IR device calls executed."
)
