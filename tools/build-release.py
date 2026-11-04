#!/usr/bin/env python3
"""Build a release image from a GSI and an APK without flashing a device."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid


ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_input(parser, path, name):
    if not path.is_file() or path.stat().st_size == 0:
        parser.error(f"Missing {name}: {path}")


def source_apk_inputs(parser):
    files = [
        ROOT / "settings.gradle.kts",
        ROOT / "build.gradle.kts",
        ROOT / "gradle.properties",
        ROOT / "a9_accessibility_service/build.gradle.kts",
        ROOT / "a9_accessibility_service/AndroidManifest.xml",
        ROOT / "tools/android-system-api-stubs/build.gradle.kts",
        ROOT / "tools/build-source-apk.sh",
        ROOT / "tools/lib/build-common.sh",
    ]
    for path in files:
        require_input(parser, path, "source APK build input")
    for name in ("a9_accessibility_service/src", "a9_accessibility_service/res",
                 "a9_accessibility_service/standalone", "tools/android-system-api-stubs/src"):
        directory = ROOT / name
        if not directory.is_dir():
            parser.error(f"Missing source APK input directory: {directory}")
        files.extend(path for path in directory.rglob("*") if path.is_file())
    return {f"apk_source:{path.relative_to(ROOT)}": path for path in sorted(files)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gsi", type=Path, help="Raw ext4 A/B GSI image")
    parser.add_argument("apk", type=Path, nargs="?", help="Pinned upstream A9 APK input")
    parser.add_argument("--source-apk", action="store_true",
                        help="Use the experimental source-built APK instead of a pinned APK")
    parser.add_argument("--vendor-image", type=Path,
                        help="Matching stock vendor image; required for IR or XRZ")
    parser.add_argument("--aosp-headers", type=Path,
                        help="Android 12 headers; required for --ir")
    parser.add_argument("--ir", action="store_true", help="Include the release IR HAL")
    parser.add_argument("--xrz", action="store_true", help="Include experimental XRZ v2 overlay")
    parser.add_argument("--output-root", type=Path, default=ROOT / "build",
                        help="Directory for a new timestamped build (default: build/)")
    args = parser.parse_args()

    require_input(parser, args.gsi, "GSI image")
    if args.source_apk:
        if args.apk is not None:
            parser.error("Do not supply a base APK with --source-apk")
        apk_inputs = source_apk_inputs(parser)
    else:
        if args.apk is None:
            parser.error("A base APK is required unless --source-apk is selected")
        require_input(parser, args.apk, "base APK")
        apk_inputs = {"base_apk": args.apk.resolve()}
    if args.ir or args.xrz:
        if args.vendor_image is None:
            parser.error("--vendor-image is required for --ir or --xrz")
        require_input(parser, args.vendor_image, "vendor image")
    if args.ir:
        if args.aosp_headers is None or not args.aosp_headers.is_dir():
            parser.error("--aosp-headers must name the Android 12 header directory for --ir")
        for header in ("hardware/consumerir.h", "hardware/hardware.h"):
            if not (args.aosp_headers / header).is_file():
                parser.error(f"Missing AOSP header: {args.aosp_headers / header}")
    output_root = args.output_root.resolve()
    for path in (args.gsi, args.apk, args.vendor_image, args.aosp_headers, output_root):
        if path is not None and any(char in str(path) for char in ('"', "\\", "\n", "\r")):
            parser.error(f"Unsupported path characters: {path}")

    try:
        output_root.mkdir(parents=True, exist_ok=True)
        run_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        build_dir = Path(tempfile.mkdtemp(prefix=f"hibreak-{run_name}-", dir=output_root))
    except OSError as error:
        parser.error(f"Cannot create build directory: {error}")

    apk = build_dir / "HiBreakEink-release.apk"
    daemon = build_dir / "a9_eink_server-release"
    base = build_dir / "HiBreakPro-release-base.img"
    apk_command = (["bash", str(ROOT / "tools/build-source-apk.sh"), str(apk)]
                   if args.source_apk else
                   ["bash", str(ROOT / "tools/build-apk.sh"), str(apk_inputs["base_apk"]), str(apk)])
    commands = [
        apk_command,
        ["bash", str(ROOT / "tools/build-daemon.sh"), str(daemon)],
        ["bash", str(ROOT / "tools/patch-gsi.sh"), str(args.gsi.resolve()),
         str(base), str(apk), str(daemon), "--release"],
    ]
    current = base
    ir_image = build_dir / "HiBreakPro-release-ir.img"
    hal = build_dir / "consumerir.hxd-release.so"
    if args.ir:
        commands.extend([
            ["bash", str(ROOT / "tools/build-ir-hal.sh"), str(hal)],
            [sys.executable, str(ROOT / "tools/add-ir-capture-to-gsi.py"),
             str(current), str(ir_image), "--vendor-image", str(args.vendor_image.resolve()),
             "--hal-module", str(hal)],
        ])
        current = ir_image
    xrz_image = build_dir / "HiBreakPro-xrz-v2-test.img"
    if args.xrz:
        commands.append([
            sys.executable, str(ROOT / "tools/add-xrz-compat-to-gsi.py"),
            str(current), str(xrz_image), "--vendor-image", str(args.vendor_image.resolve()),
        ])
        current = xrz_image

    input_files = {"gsi": args.gsi.resolve(), **apk_inputs}
    if args.vendor_image:
        input_files["vendor_image"] = args.vendor_image.resolve()
    if args.ir:
        for header in ("hardware/consumerir.h", "hardware/hardware.h"):
            path = args.aosp_headers / header
            input_files[f"aosp_header:{header}"] = path
    manifest = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "options": {"ir": args.ir, "xrz_v2": args.xrz, "release": True},
        "inputs": {
            name: {"path": str(path), "sha256": sha256(path)}
            for name, path in input_files.items()
        },
        "outputs": {},
        "final_image": str(current),
    }
    if args.source_apk:
        manifest["options"]["source_apk"] = True

    try:
        child_environment = os.environ.copy()
        if args.ir:
            child_environment["AOSP_HEADERS"] = str(args.aosp_headers.resolve())
        for command in commands:
            subprocess.run(command, cwd=ROOT, env=child_environment, check=True)
        outputs = [apk, daemon, base]
        if args.ir:
            outputs.extend((hal, ir_image))
        if args.xrz:
            outputs.append(xrz_image)
        for path in outputs:
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"Build step did not produce expected output: {path}")
            manifest["outputs"][path.name] = {"path": str(path), "sha256": sha256(path)}
        manifest_path = build_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            raise SystemExit(f"Build command failed with exit status {error.returncode}; partial files remain in {build_dir}")
        raise SystemExit(f"{error}; partial files remain in {build_dir}")

    print(f"Final image: {current}")
    print(f"Manifest: {manifest_path}")
    print("No device was accessed or flashed.")


if __name__ == "__main__":
    main()
