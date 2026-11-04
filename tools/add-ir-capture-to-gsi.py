#!/usr/bin/env python3
"""Add a NEC IR HAL to an ext4 GSI; diagnostics and test apps are explicit opt-ins."""

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.hibreak.elf import validate_hal_module, validate_static_arm64_executable
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
    parser.add_argument("binary", nargs="?", type=Path,
                        help="Legacy explicit opt-in for diagnostics; prefer --diagnostics-binary")
    parser.add_argument("--diagnostics-binary", type=Path,
                        help="Opt in to capture/camera services with an NDK-built hxd-learn")
    parser.add_argument("--vendor-image", required=True, type=Path, help="Matching stock vendor ext4 image, read-only")
    parser.add_argument("--secilc", default="secilc", help="Host CIL compiler")
    parser.add_argument("--check-only", action="store_true", help="Validate merged policy without producing an image")
    parser.add_argument("--remote-apk", type=Path, help="Optional HiBreak IR Test app; enables fixed TCL transmit service")
    parser.add_argument("--api-test-apk", type=Path, help="Opt in to the ordinary Android IR API Test app")
    parser.add_argument("--hal-module", type=Path, help="Experimental arm64 NEC/NECext legacy consumerir adapter")
    args = parser.parse_args()
    if args.binary and args.diagnostics_binary:
        parser.error("Choose either positional binary or --diagnostics-binary, not both")
    args.binary = args.diagnostics_binary or args.binary
    if args.binary and not args.diagnostics_binary:
        print(
            "Deprecated: pass the capture binary with --diagnostics-binary; "
            "the positional form will be removed in a future release.",
            file=sys.stderr,
        )
    if args.remote_apk and not args.binary:
        parser.error("--remote-apk requires --diagnostics-binary")
    if not args.binary and not args.hal_module:
        parser.error("Select --hal-module (release) or --diagnostics-binary (diagnostics)")
    for tool in ("debugfs", "e2fsck", "resize2fs", "dumpe2fs", "cp", args.secilc):
        if not shutil.which(tool):
            parser.error(f"Missing dependency: {tool}")
    if args.hal_module and not shutil.which("readelf"):
        parser.error("Missing dependency: readelf (binutils)")
    for path in filter(None, (args.source, args.output, args.binary, args.vendor_image, ROOT,
                             Path(tempfile.gettempdir()), args.remote_apk, args.api_test_apk)):
        if any(char in str(path) for char in ('"', "\\", "\n", "\r")):
            parser.error(f"Unsupported path characters: {path}")
    for path in filter(None, (args.source, args.binary, args.vendor_image,
                             args.remote_apk, args.api_test_apk)):
        if not path.is_file() or path.stat().st_size == 0:
            parser.error(f"Missing input: {path}")
    if args.remote_apk and (not args.remote_apk.is_file() or args.remote_apk.stat().st_size == 0):
        parser.error(f"Missing remote APK: {args.remote_apk}")
    if args.hal_module:
        if any(char in str(args.hal_module) for char in ('"', "\\", "\n", "\r")):
            parser.error("Unsupported HAL module path characters")
        if not args.hal_module.is_file():
            parser.error(f"Missing HAL module: {args.hal_module}")
        validate_hal_module(args.hal_module)
    if os.path.lexists(args.output):
        parser.error(f"Refusing to overwrite: {args.output}")
    if args.binary:
        try:
            validate_static_arm64_executable(args.binary)
        except ValueError as error:
            parser.error(str(error))
    with tempfile.TemporaryDirectory(prefix="hibreak-ir-") as directory:
        work = Path(directory)
        if args.hal_module:
            stock = extract(args.vendor_image, "/lib64/hw/consumerir.common.so", work / "stock-ir.so")
            service = extract(args.vendor_image, "/etc/init/android.hardware.ir@1.0-service.rc", work / "stock-ir.rc")
            if stock.read_bytes()[:6] != b"\x7fELF\x02\x01" or "class hal" not in service.read_text():
                raise ValueError("Expected arm64 legacy consumerir.common.so and class-hal IR service")
            platform, contexts, inputs = prepare_policy(args.source, args.vendor_image, work, args.secilc,
                                                        remote=bool(args.remote_apk), hal=True,
                                                        diagnostics=bool(args.binary))
        elif args.remote_apk:
            platform, contexts, inputs = prepare_policy(args.source, args.vendor_image, work, args.secilc,
                                                        remote=True, diagnostics=True)
        else:
            platform, contexts, inputs = prepare_policy(args.source, args.vendor_image, work, args.secilc,
                                                        diagnostics=True)
        remote_contexts = []
        if args.remote_apk:
            for name, suffix in (("plat_seapp_contexts", "seapp-contexts"), ("plat_property_contexts", "property-contexts")):
                context = extract(args.source, f"{POLICY}/{name}", work / name)
                context.write_text(context.read_text() + "\n" +
                                   (ROOT / f"tools/ir/hibreak-ir-remote-{suffix}").read_text())
                remote_contexts.append((context, f"{POLICY}/{name}", "0100644", "system_file"))
        print("Merged GSI + stock vendor IR policy compiled; no new neverallow conflicts.")
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
            if args.binary:
                for source, dest, mode, label in (
                    (args.binary, "system/bin/hxd-learn", "0100755", "hibreak_ir_capture_exec"),
                    (ROOT / "tools/ir/hibreak-ir-capture.rc", "system/etc/init/hibreak-ir-capture.rc", "0100644", "system_file"),
                ):
                    install(args.output, source, dest, mode, f"u:object_r:{label}:s0", work)
            if args.hal_module:
                for source, dest, label in (
                    (args.hal_module, "system/lib64/consumerir.hxd.so", "hibreak_ir_hal_file"),
                    (ROOT / "tools/ir/hibreak-ir-hal.rc", "system/etc/init/hibreak-ir-hal.rc", "system_file"),
                ):
                    install(args.output, source, dest, "0100644", f"u:object_r:{label}:s0", work)
            if args.remote_apk:
                install_app(args.output, args.remote_apk, "system/priv-app/HiBreakIrRemote",
                            "HiBreakIrRemote.apk", work)
                for source, dest, mode, label in [
                    *remote_contexts,
                    (ROOT / "tools/ir/hibreak-ir-remote.rc", "system/etc/init/hibreak-ir-remote.rc", "0100644", "system_file"),
                ]:
                    install(args.output, source, dest, mode, f"u:object_r:{label}:s0", work)
            if args.api_test_apk:
                install_app(args.output, args.api_test_apk, "system/app/HiBreakIrApiTest",
                            "HiBreakIrApiTest.apk", work)
            image.shrink_and_check(args.output)
        except BaseException:
            args.output.unlink()
            raise
    kind = "NEC HAL" if args.hal_module else "remote" if args.remote_apk else "capture"
    print(f"Verified IR {kind} test image: {args.output}")
    print("No flashing, ADB access, learning, or IR transmission was performed.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stdout.decode(errors="replace") + error.stderr.decode(errors="replace"), file=sys.stderr)
        raise SystemExit(str(error))
