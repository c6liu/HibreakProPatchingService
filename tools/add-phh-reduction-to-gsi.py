#!/usr/bin/env python3
"""Apply the exact host-tested PHH grant reduction to a separate experimental image."""

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.hibreak import image
from tools.hibreak.policy import compile_pair, neverallow_failures, prepare_ir_policy


EXT_POLICY = "system/system_ext/etc/selinux/system_ext_sepolicy.cil"
EXT_SHA256 = "a9e1954bb0bb99e2346133c712133478dde536f6a9da52fc945ea4e9146a4036"
REMOVED_LINES = frozenset((
    806, 827, 833, 886, 927, 928, 931, 934, 945, 946, 949, 958, 972, 984,
    997, 1000, 1003, 1006, 1012, 1018, 1021, 1024, 1033, 1036, 1048, 1049,
    1050, 1051, 1052, 1053, 1054, 1057, 1058, 1059, 1060, 1061, 1067, 1068,
    1069, 1070, 1071, 1075, 1076, 1077, 1078, 1084, 1085, 1086, 1087,
    1093, 1099, 1108, 1114, 1126, 1132, 1135, 1136, 1139, 1142, 1148,
    1150, 1153, 1155, 1158, 1159, 1171, 1179, 1191, 1194, 1197,
))


def reduce_policy(content):
    # Line selection is safe only for this byte-identical, host-tested policy.
    if hashlib.sha256(content).hexdigest() != EXT_SHA256:
        raise ValueError("Unsupported system-ext policy: requires the exact EvoX 11.11 20260920 baseline")
    lines = content.decode().splitlines(keepends=True)
    for number in REMOVED_LINES:
        rule = lines[number - 1]
        if not rule.startswith("(allow phhsu_daemon ") or rule.count("(") != rule.count(")"):
            raise ValueError(f"Unexpected PHH grant at line {number}")
        lines[number - 1] = "; experiment removed grant\n"
    return "".join(lines).encode()


def prepare_reduction(source, vendor, work, compiler, *, parallel_compile=False):
    _, _, inputs = prepare_ir_policy(
        source, vendor, work, compiler, allow_existing_ir=True, parallel_compile=parallel_compile,
    )
    ext = work / "ext.cil"
    if ext not in inputs:
        raise ValueError("GSI has no system-ext policy")
    ext.write_bytes(reduce_policy(ext.read_bytes()))
    command = [compiler, "-m", "-M", "true", "-G", "-c", "30", *map(str, inputs),
               "-o", str(work / "reduced.policy"), "-f", str(work / "reduced.contexts")]
    failures = (compile_pair(command) if parallel_compile
                else neverallow_failures(subprocess.run(command, capture_output=True)))
    ordinary = sum(block.startswith("neverallow ") for block in failures)
    extended = len(failures) - ordinary
    if (ordinary, extended) != (371, 15):
        raise ValueError(
            f"Unexpected reduced policy conflicts: ordinary={ordinary}, extended={extended}; "
            "expected 371 and 15 for the tested GSI/vendor pair"
        )
    if not parallel_compile:
        image.run(*command, "-N")
    digest = hashlib.sha256()
    for path in inputs:
        digest.update(path.read_bytes())
    digest_file = work / "policy-digest"
    digest_file.write_text(digest.hexdigest() + "\n")
    vendor_digest = image.extract(
        vendor, "/etc/selinux/precompiled_sepolicy.plat_sepolicy_and_mapping.sha256",
        work / "vendor-policy-digest",
    ).read_text().strip()
    if not re.fullmatch(r"[0-9a-fA-F]{64}", vendor_digest):
        raise ValueError("Invalid vendor precompiled policy digest")
    if vendor_digest.lower() == digest.hexdigest():
        raise ValueError("Reduced policy digest matches vendor precompiled policy")
    print("WARNING: EXPERIMENTAL PHH reduction removes 70 root grants; 386 conflicts remain.")
    print("phhsu_daemon remains permissive. This is not hardening and is not device-validated.")
    return ext, digest_file


def build_image(source, output, files, work):
    if os.path.lexists(output):
        raise ValueError(f"Refusing to overwrite: {output}")
    if len(files) != 2:
        raise ValueError("Expected exactly two PHH policy inputs")
    complete = False
    try:
        image.copy_and_grow(source, output, 32 * 1024 * 1024)
        for file, destination in zip(files, (
            EXT_POLICY, f"{image.POLICY}/plat_sepolicy_and_mapping.sha256",
        )):
            image.install(output, file, destination, "0100644", "u:object_r:system_file:s0", work)
        image.shrink_and_check(output, strict_final=True)
        complete = True
    finally:
        if not complete:
            output.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--vendor-image", required=True, type=Path)
    parser.add_argument("--secilc", default="secilc")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    for tool in ("debugfs", "e2fsck", "resize2fs", "dumpe2fs", "cp", args.secilc):
        if not tool or not shutil.which(tool):
            parser.error(f"Missing dependency: {tool}")
    for path in (args.source, args.vendor_image):
        if not path.is_file() or path.stat().st_size == 0:
            parser.error(f"Missing input: {path}")
    for path in (args.source, args.vendor_image, args.output, Path(tempfile.gettempdir())):
        if any(char in str(path) for char in ('"', "\\", "\n", "\r")):
            parser.error(f"Unsupported path characters: {path}")
    if os.path.lexists(args.output):
        parser.error(f"Refusing to overwrite: {args.output}")
    with tempfile.TemporaryDirectory(prefix="hibreak-phh-reduction-") as directory:
        work = Path(directory)
        files = prepare_reduction(args.source, args.vendor_image, work, args.secilc)
        if args.check_only:
            print("Preflight passed; no image written.")
            return
        build_image(args.source, args.output, files, work)
    print(f"Verified experimental PHH-reduced image: {args.output}")
    print("No vendor partition was modified and no device was accessed.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            print(((error.stdout or b"") + (error.stderr or b"")).decode(errors="replace"),
                  file=sys.stderr)
        raise SystemExit(str(error))
