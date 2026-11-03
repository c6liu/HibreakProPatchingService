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
print(
    f"Verified {len(cases)} native routine vectors, {len(extended_cases)} extended packets, "
    f"{len(compact_cases)} compact database packets, and {len(identifier_cases)} identifier packets; "
    "no JNI callbacks, transport, or IR device calls executed."
)
