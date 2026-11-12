#!/usr/bin/env python3
"""Add the NEC IR HAL to an ext4 GSI; the API test app is an explicit opt-in."""

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.hibreak.elf import validate_hal_module
from tools.hibreak import image
from tools.hibreak.image import (
    POLICY, extract, fsck, image_exists, install, install_app, run,
)
from tools.hibreak.policy import (
    neverallow_failures, prepare_ir_policy as prepare_policy,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Raw ext4 GSI, optionally already display-patched")
    parser.add_argument("output", type=Path, help="New image; never overwritten")
    parser.add_argument("--vendor-image", required=True, type=Path, help="Matching stock vendor ext4 image, read-only")
    parser.add_argument("--secilc", default="secilc", help="Host CIL compiler")
    parser.add_argument("--check-only", action="store_true", help="Validate merged policy without producing an image")
    parser.add_argument("--api-test-apk", type=Path, help="Opt in to the ordinary Android IR API Test app")
    parser.add_argument("--hal-module", required=True, type=Path,
                        help="Arm64 NEC/NECext legacy consumerir adapter")
    args = parser.parse_args()
    for tool in ("debugfs", "e2fsck", "resize2fs", "dumpe2fs", "cp", "readelf", args.secilc):
        if not shutil.which(tool):
            parser.error(f"Missing dependency: {tool}")
    for path in filter(None, (args.source, args.output, args.vendor_image, args.hal_module, ROOT,
                             Path(tempfile.gettempdir()), args.api_test_apk)):
        if any(char in str(path) for char in ('"', "\\", "\n", "\r")):
            parser.error(f"Unsupported path characters: {path}")
    for path in filter(None, (args.source, args.vendor_image, args.api_test_apk)):
        if not path.is_file() or path.stat().st_size == 0:
            parser.error(f"Missing input: {path}")
    if not args.hal_module.is_file():
        parser.error(f"Missing HAL module: {args.hal_module}")
    validate_hal_module(args.hal_module)
    if os.path.lexists(args.output):
        parser.error(f"Refusing to overwrite: {args.output}")
    with tempfile.TemporaryDirectory(prefix="hibreak-ir-") as directory:
        work = Path(directory)
        stock = extract(args.vendor_image, "/lib64/hw/consumerir.common.so", work / "stock-ir.so")
        service = extract(args.vendor_image, "/etc/init/android.hardware.ir@1.0-service.rc", work / "stock-ir.rc")
        if stock.read_bytes()[:6] != b"\x7fELF\x02\x01" or "class hal" not in service.read_text():
            raise ValueError("Expected arm64 legacy consumerir.common.so and class-hal IR service")
        platform, contexts, inputs = prepare_policy(args.source, args.vendor_image, work, args.secilc, hal=True)
        print("Merged GSI + stock vendor IR policy compiled; no new neverallow/neverallowx conflicts.")
        if args.check_only:
            return
        # This is a cache-buster for our overlay, not an AOSP build-system hash.
        digest = hashlib.sha256()
        for path in inputs:
            digest.update(path.read_bytes())
        digest_file = work / "policy-digest"
        digest_file.write_text(digest.hexdigest() + "\n")
        image.copy_and_grow(args.source, args.output, 32 * 1024 * 1024)
        try:
            for source, dest, mode, label in (
                (platform, f"{POLICY}/plat_sepolicy.cil", "0100644", "system_file"),
                (contexts, f"{POLICY}/plat_file_contexts", "0100644", "system_file"),
                (digest_file, f"{POLICY}/plat_sepolicy_and_mapping.sha256", "0100644", "system_file"),
            ):
                install(args.output, source, dest, mode, f"u:object_r:{label}:s0", work)
            for source, dest, label in (
                (args.hal_module, "system/lib64/consumerir.hxd.so", "hibreak_ir_hal_file"),
                (ROOT / "tools/ir/hibreak-ir-hal.rc", "system/etc/init/hibreak-ir-hal.rc", "system_file"),
            ):
                install(args.output, source, dest, "0100644", f"u:object_r:{label}:s0", work)
            if args.api_test_apk:
                install_app(args.output, args.api_test_apk, "system/app/HiBreakIrApiTest",
                            "HiBreakIrApiTest.apk", work)
            image.shrink_and_check(args.output)
        except BaseException:
            args.output.unlink()
            raise
    print(f"Verified IR NEC HAL image: {args.output}")
    print("No flashing, ADB access, or IR transmission was performed.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stdout.decode(errors="replace") + error.stderr.decode(errors="replace"), file=sys.stderr)
        raise SystemExit(str(error))
