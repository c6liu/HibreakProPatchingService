"""Validation for native IR HAL modules."""

import re
import struct
import subprocess


def validate_hal_module(path):
    module = path.read_bytes()
    if (len(module) < 64 or module[:7] != b"\x7fELF\x02\x01\x01" or
            module[16:20] != b"\x03\x00\xb7\x00"):
        raise ValueError("Expected an arm64 little-endian shared HAL module")
    phoff = struct.unpack_from("<Q", module, 32)[0]
    phsize, phnum = struct.unpack_from("<HH", module, 54)
    if phsize != 56 or not phnum or phoff < 64 or phoff + phsize * phnum > len(module):
        raise ValueError("Invalid HAL ELF program headers")
    segments = [struct.unpack_from("<IIQQQQQQ", module, phoff + index * phsize)
                for index in range(phnum)]
    for kind, flags, offset, virtual, physical, filesz, memsz, alignment in segments:
        if offset + filesz > len(module) or (kind == 1 and filesz > memsz):
            raise ValueError("Truncated or invalid HAL ELF segment")
    loads = [segment for segment in segments if segment[0] == 1]
    dynamic = [segment for segment in segments if segment[0] == 2]
    if not loads or not any(segment[1] & 1 for segment in loads) or len(dynamic) != 1:
        raise ValueError("HAL requires executable LOAD and DYNAMIC segments")
    if any(segment[0] == 3 for segment in segments):
        raise ValueError("HAL must be a shared library, not a PIE executable")
    _, _, offset, virtual, _, size, _, _ = dynamic[0]
    if not size or size % 16 or not any(
        load[3] <= virtual and virtual + size <= load[3] + load[5] and
        offset == load[2] + virtual - load[3] for load in loads
    ) or not any(struct.unpack_from("<qQ", module, pos)[0] == 0
                 for pos in range(offset, offset + size, 16)):
        raise ValueError("Invalid HAL dynamic table")
    symbols = subprocess.run(
        ["readelf", "--dyn-syms", "--wide", str(path)], check=True, capture_output=True,
    ).stdout.decode()
    if not re.search(r"\b(?:248|0xf8)\s+OBJECT\s+GLOBAL\s+DEFAULT\s+[1-9]\d*\s+HMI\s*$",
                     symbols, re.M):
        raise ValueError("HAL must export the 248-byte arm64 consumerir HMI object")
    details = subprocess.run(
        ["readelf", "--dynamic", "--wide", str(path)], check=True, capture_output=True,
    ).stdout.decode()
    needed = set(re.findall(r"\(NEEDED\).*?\[([^]]+)\]", details))
    unsupported = needed - {"libc.so", "libdl.so", "liblog.so", "libm.so"}
    if unsupported:
        raise ValueError("Unsupported HAL dependencies: " + ", ".join(sorted(unsupported)))
    if "(TEXTREL)" in details or re.search(r"\(FLAGS\).*TEXTREL", details):
        raise ValueError("HAL must not contain text relocations")
