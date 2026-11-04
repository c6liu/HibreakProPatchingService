#!/usr/bin/env python3
"""Build a release image from a GSI and an APK without flashing a device."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
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
    apk_mode = parser.add_mutually_exclusive_group()
    apk_mode.add_argument("--source-apk", action="store_true",
                          help="Build the experimental APK from checked-in source (default)")
    apk_mode.add_argument("--built-apk", type=Path,
                          help="Reuse an already signed APK unchanged, without rebuilding")
    parser.add_argument("--vendor-image", type=Path, default=os.environ.get("VENDOR"),
                        help="Matching stock vendor image; required for IR or XRZ")
    parser.add_argument("--aosp-headers", type=Path, default=os.environ.get("AOSP_HEADERS"),
                        help="Android 12 headers; required for --ir")
    parser.add_argument("--ndk", type=Path, default=os.environ.get("ANDROID_NDK_HOME"),
                        help="Android NDK directory (default: ANDROID_NDK_HOME)")
    parser.add_argument("--secilc", default=os.environ.get("SECILC", "secilc"),
                        help="Policy compiler for both overlays (default: SECILC or secilc)")
    parser.add_argument("--ir", action="store_true", help="Include the release IR HAL")
    parser.add_argument("--xrz", action="store_true", help="Include experimental XRZ v2 overlay")
    parser.add_argument("--output-root", type=Path, default=ROOT / "build",
                        help="Directory for a new timestamped build (default: build/)")
    args = parser.parse_args()
    if args.apk is None and args.built_apk is None:
        args.source_apk = True

    require_input(parser, args.gsi, "GSI image")
    if args.apk is not None and (args.source_apk or args.built_apk is not None):
        parser.error("Do not supply a base APK with --source-apk or --built-apk")
    if args.built_apk is not None:
        require_input(parser, args.built_apk, "built APK")
        apk_inputs = {"built_apk": args.built_apk.resolve()}
    elif args.source_apk:
        apk_inputs = source_apk_inputs(parser)
    elif args.apk is not None:
        require_input(parser, args.apk, "base APK")
        apk_inputs = {"base_apk": args.apk.resolve()}
    else:
        parser.error("Select a base APK, --source-apk, or --built-apk")
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
    for path in (args.gsi, args.apk, args.built_apk, args.vendor_image,
                 args.aosp_headers, args.ndk, output_root):
        if path is not None and any(char in str(path) for char in ('"', "\\", "\n", "\r")):
            parser.error(f"Unsupported path characters: {path}")

    verification = None
    expected_cert = os.environ.get("APK_RELEASE_CERT_SHA256", "").replace(":", "")
    if args.built_apk is not None:
        if expected_cert and not re.fullmatch(r"[0-9a-fA-F]{64}", expected_cert):
            parser.error("APK_RELEASE_CERT_SHA256 must be a 64-digit SHA-256 fingerprint")
        signer = Path(os.environ.get("APK_SIGNER_JAR", ROOT / "local/uber-apk-signer.jar"))
        require_input(parser, signer, "APK signer")
        verification = ["java", "-jar", str(signer.resolve()), "--onlyVerify"]
        if expected_cert:
            verification.extend(("--verifySha256", expected_cert))

    try:
        output_root.mkdir(parents=True, exist_ok=True)
        run_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        build_dir = Path(tempfile.mkdtemp(prefix=f"hibreak-{run_name}-", dir=output_root))
    except OSError as error:
        parser.error(f"Cannot create build directory: {error}")

    apk = build_dir / "HiBreakEink-release.apk"
    daemon = build_dir / "a9_eink_server-release"
    base = build_dir / "HiBreakPro-release-base.img"
    commands = [
        ["bash", str(ROOT / "tools/build-daemon.sh"), str(daemon)],
        ["bash", str(ROOT / "tools/patch-gsi.sh"), str(args.gsi.resolve()),
         str(base), str(apk), str(daemon), "--release"],
    ]
    if args.source_apk:
        commands.insert(0, ["bash", str(ROOT / "tools/build-source-apk.sh"), str(apk)])
    elif args.built_apk is None:
        commands.insert(0, ["bash", str(ROOT / "tools/build-apk.sh"),
                            str(apk_inputs["base_apk"]), str(apk)])
    current = base
    ir_image = build_dir / "HiBreakPro-release-ir.img"
    hal = build_dir / "consumerir.hxd-release.so"
    if args.ir:
        commands.extend([
            ["bash", str(ROOT / "tools/build-ir-hal.sh"), str(hal)],
            [sys.executable, str(ROOT / "tools/add-ir-capture-to-gsi.py"),
             str(current), str(ir_image), "--vendor-image", str(args.vendor_image.resolve()),
             "--hal-module", str(hal), "--secilc", args.secilc],
        ])
        current = ir_image
    xrz_image = build_dir / "HiBreakPro-xrz-v2-test.img"
    if args.xrz:
        commands.append([
            sys.executable, str(ROOT / "tools/add-xrz-compat-to-gsi.py"),
            str(current), str(xrz_image), "--vendor-image", str(args.vendor_image.resolve()),
            "--secilc", args.secilc,
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
    if args.built_apk is not None:
        manifest["options"]["reuse_built_apk"] = True
        if expected_cert:
            manifest["apk_certificate_sha256"] = expected_cert.lower()

    try:
        child_environment = os.environ.copy()
        if args.ndk is not None:
            child_environment["ANDROID_NDK_HOME"] = str(args.ndk.resolve())
        if args.ir:
            child_environment["AOSP_HEADERS"] = str(args.aosp_headers.resolve())
        if args.built_apk is not None:
            with args.built_apk.open("rb") as source, apk.open("xb") as target:
                shutil.copyfileobj(source, target)
            if sha256(apk) != manifest["inputs"]["built_apk"]["sha256"]:
                raise ValueError("Built APK changed while being copied")
            if verification is not None:
                subprocess.run([*verification, "-a", str(apk)], cwd=ROOT,
                               env=child_environment, check=True)
        for command in commands:
            print(f"Running: {Path(command[1]).name}", flush=True)
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
