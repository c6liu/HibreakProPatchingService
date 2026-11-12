#!/usr/bin/env python3
# /// script
# dependencies = ["unicorn==2.1.4"]
# ///
"""Exercise the stock HXD driver offline with mocked kernel/GPIO boundaries."""

import argparse
import hashlib
import struct
from collections import deque
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM64, UC_HOOK_CODE, UC_MODE_ARM
from unicorn.arm64_const import (
    UC_ARM64_REG_LR,
    UC_ARM64_REG_PC,
    UC_ARM64_REG_SP,
    UC_ARM64_REG_X0,
    UC_ARM64_REG_X1,
    UC_ARM64_REG_X2,
    UC_ARM64_REG_X8,
)

IMAGE_BASE = 0x08080000
DRIVER_START = 0x08C56A08
DRIVER_END = 0x08C584F0
FILE = 0x100000
PRIVATE = 0x101000
USER = 0x102000
TASK = 0x103000
STOP = 0x104000
PINS = 0x0A8129F0
MODE = 0x0A8129D4
REGISTERS = (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2)


class Driver:
    def __init__(self, image):
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.uc.mem_map(IMAGE_BASE, 0x02800000)
        self.uc.mem_write(IMAGE_BASE, image)
        self.uc.mem_map(FILE, 0x10000)
        self.uc.mem_write(FILE + 0xC8, struct.pack("<Q", PRIVATE))
        self.uc.mem_write(TASK + 8, struct.pack("<Q", 0x7FFFFFFFFFFFFF))
        self.uc.mem_write(PINS, struct.pack("<4I", 105, 104, 106, 190))
        self.uc.hook_add(UC_HOOK_CODE, self.hook)
        self.events = []
        self.incoming = deque()
        self.bits = deque()
        self.ready = 1
        self.copy_fault = False
        self.mock_bytes = True

    def hook(self, uc, address, size, _):
        if not DRIVER_START <= address < DRIVER_END:
            raise RuntimeError(f"Execution left the driver at {address:#x}")
        word = struct.unpack("<I", uc.mem_read(address, 4))[0]
        if word == 0xD5384108:  # mrs x8, SP_EL0: synthetic current task.
            uc.reg_write(UC_ARM64_REG_X8, TASK)
            uc.reg_write(UC_ARM64_REG_PC, address + 4)
            return
        if word & 0xFC000000 != 0x94000000:
            return
        displacement = word & 0x03FFFFFF
        if displacement & 0x02000000:
            displacement -= 0x04000000
        target = address + displacement * 4
        x0, x1, x2 = (uc.reg_read(reg) for reg in REGISTERS)
        result = 0
        if target in (0x0829797C, 0x09265810, 0x083F6244, 0x082C1574):
            pass  # printk, delay, object-size check, ktime_get.
        elif target == 0x086AAA58:
            result = x0  # Synthetic GPIO descriptor is its pin number.
        elif target == 0x086AC600:
            self.events.append(("out", x0, x1))
        elif target == 0x086AC2E0:
            self.events.append(("in", x0))
        elif target == 0x086AD568:
            result = self.ready if x0 == 106 else self.bits.popleft()
        elif target in (0x0808E700, 0x0808ED40):
            if self.copy_fault:
                result = x2
            else:
                uc.mem_write(x0, bytes(uc.mem_read(x1, x2)))
        elif target == 0x0808F480:
            uc.mem_write(x0, bytes([x1 & 255]) * x2)
            result = x0
        elif self.mock_bytes and target == 0x08C57964:
            self.events.append(("write", x0 & 255))
            result = 1  # Sampled high ACK result, deliberately not success.
        elif self.mock_bytes and target == 0x08C57A78:
            uc.mem_write(x0, bytes([self.incoming.popleft()]))
            self.events.append(("read",))
        elif self.mock_bytes and target in (0x08C577E8, 0x08C57B88):
            self.events.append(("start" if target == 0x08C577E8 else "stop",))
        elif DRIVER_START <= target < DRIVER_END:
            return
        else:
            raise RuntimeError(f"Unmocked kernel call {target:#x} at {address:#x}")
        uc.reg_write(UC_ARM64_REG_X0, result)
        uc.reg_write(UC_ARM64_REG_PC, address + 4)

    def call(self, address, *args):
        self.events.clear()
        for reg, value in zip(REGISTERS, args):
            self.uc.reg_write(reg, value)
        self.uc.reg_write(UC_ARM64_REG_SP, FILE + 0xFFF0)
        self.uc.reg_write(UC_ARM64_REG_LR, STOP)
        self.uc.emu_start(address, STOP, count=200000)
        assert self.uc.reg_read(UC_ARM64_REG_PC) == STOP, "Instruction limit reached"
        result = self.uc.reg_read(UC_ARM64_REG_X0)
        return result if result < 1 << 63 else result - (1 << 64)

    def bus(self):
        return [event for event in self.events if event[0] in ("start", "write", "read", "stop")]


def verify(image):
    driver = Driver(image)
    for count in (1, 3, 112, 232, 255, 256):
        payload = bytes(index & 255 for index in range(count))
        driver.uc.mem_write(USER, payload)
        driver.incoming = deque([0xA5])
        assert driver.call(0x08C56FD4, FILE, USER, count) == min(count, 255)
        assert driver.bus() == (
            [("read",), ("start",)]
            + [("write", value) for value in payload[:255]]
            + [("stop",)]
        )
    print("PASS: writes preserve bytes, clamp at 255, and ignore high ACK results")

    for command, mode, read_command in ((b"\x30\x10\x40", 0, 0x52), (b"\x30\x20\x50", 1, 0x62)):
        driver.uc.mem_write(USER, command)
        driver.incoming = deque([0])
        assert driver.call(0x08C56FD4, FILE, USER, 3) == 3
        assert driver.uc.mem_read(MODE, 1) == bytes([mode])
        for count in (1, 2, 110, 230, 255, 256):
            length = min(count, 255)
            response = bytes([0] + [index & 255 for index in range(1, length)] + [0xEE])
            driver.incoming = deque(response)
            driver.uc.mem_write(USER, b"\xCC" * 256)
            assert driver.call(0x08C56A08, FILE, USER, count) == length
            assert not driver.incoming, "Read clocks one extra byte beyond returned data"
            assert bytes(driver.uc.mem_read(USER, length + 1)) == response[:length] + b"\xCC"
            assert driver.bus() == (
                [("start",), ("write", 0x30), ("write", read_command), ("start",), ("write", 0x31)]
                + [("read",)] * (length + 1)
                + [("stop",)]
            )
    print("PASS: both learning modes select read commands and return exact buffer layout")

    driver.ready = 0
    driver.incoming.clear()
    assert driver.call(0x08C56A08, FILE, USER, 110) == 0
    assert not driver.bus()
    driver.ready = 1
    driver.incoming = deque([1])
    assert driver.call(0x08C56A08, FILE, USER, 110) == -1
    driver.copy_fault = True
    driver.incoming = deque([0])
    assert driver.call(0x08C56FD4, FILE, USER, 3) == -14
    driver.incoming = deque(bytes(111))
    assert driver.call(0x08C56A08, FILE, USER, 110) == -14
    driver.copy_fault = False
    assert driver.call(0x08C56A08, FILE, USER, 0) == 0
    assert not driver.events
    print("PASS: not-ready, nonzero response, copy faults, and zero-length read paths")

    for command, pin, level in (
        (0x8002, 106, 1), (0x8003, 106, 0),
        (0x8005, 105, 1), (0x8006, 105, 0), (0x8007, 104, 1),
        (0x8008, 104, 0),
    ):
        for argument in (0, 38000):
            assert driver.call(0x08C574DC, FILE, command, argument) == 0
            assert driver.events == [("out", pin, level), ("in", 106)], (command, driver.events)
    for command in (0x8001, 0x8004, 0x8009, 0xDEADBEEF):
        assert driver.call(0x08C574DC, FILE, command, 38000) == -25
        assert not driver.events
    print("PASS: six GPIO ioctls ignore argument; 0x8004 and unknown commands return ENOTTY")

    driver.uc.mem_write(USER, b"\x30\x30\x60")
    driver.incoming = deque([0])
    assert driver.call(0x08C56FD4, FILE, USER, 3) == 3
    assert driver.bus() == [
        ("read",), ("start",), ("write", 0x30), ("write", 0x30), ("write", 0x60), ("stop",)
    ]
    for command, pin, level in ((0x8005, 105, 1), (0x8007, 104, 1), (0x8008, 104, 0), (0x8007, 104, 1)):
        assert driver.call(0x08C574DC, FILE, command, 0) == 0
        assert driver.events == [("out", pin, level), ("in", 106)]
    print("PASS: candidate 30 30 60 command and SDA/SCL controls reach mocked pins only")

    driver.mock_bytes = False
    for value in range(256):
        driver.bits = deque([1])
        assert driver.call(0x08C57964, value) == 1
        data = [event[2] for event in driver.events if event[:2] == ("out", 105)]
        assert data == [(value >> shift) & 1 for shift in range(7, -1, -1)]
        assert not driver.bits
        driver.bits = deque((value >> shift) & 1 for shift in range(7, -1, -1))
        assert driver.call(0x08C57A78, USER) == 0
        assert driver.uc.mem_read(USER, 1) == bytes([value])
        assert not driver.bits
    print("PASS: all 256 byte values transmit and receive eight bits MSB-first")
    assert driver.call(0x08C57CE0) == 0
    assert driver.events == [("in", 106), ("out", 105, 1), ("out", 104, 1), ("in", 104)]
    print("PASS: GPIO initialization sets idle directions without a configuration packet")
    driver.mock_bytes = True
    driver.call(0x08C57FF4)
    assert driver.bus() == [
        ("start",), ("write", 0x30), ("write", 0x10), ("write", 0x40), ("stop",)
    ]
    print("PASS: standalone learning helper sends only the known 30 10 40 command")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Decompressed stock boot_a kernel Image")
    args = parser.parse_args()
    if not __debug__:
        parser.error("Run without Python optimization: this harness requires assertions")
    image = args.image.read_bytes()
    if hashlib.sha256(image).hexdigest() != (
        "9e6d27d5ff9f7c091fdee9bcbc00211adc3d73a41c4ac5e64ce52ccb2fad652c"
    ):
        parser.error("Kernel hash differs from the analyzed stock build")
    verify(image)


if __name__ == "__main__":
    main()
