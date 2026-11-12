#!/usr/bin/env python3
"""Build a release image from a GSI and an APK without flashing a device."""

import argparse
from concurrent.futures import ThreadPoolExecutor
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


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.hibreak.tested_stages import GSI_SHA256, VENDOR_SHA256
from tools.hibreak import release_pipeline


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
        ROOT / "tools/build/build-source-apk.sh",
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
    apk_mode = parser.add_mutually_exclusive_group()
    apk_mode.add_argument("--source-apk", action="store_true",
                          help="Build the APK from checked-in source (default)")
    apk_mode.add_argument("--built-apk", type=Path,
                          help="Reuse an already signed source-built APK unchanged, without rebuilding")
    parser.add_argument("--vendor-image", type=Path, default=os.environ.get("VENDOR"),
                        help="Matching stock vendor image; required for IR or XRZ")
    parser.add_argument("--aosp-headers", type=Path, default=os.environ.get("AOSP_HEADERS"),
                        help="Android 12 headers; required for --ir")
    parser.add_argument("--ndk", type=Path, default=os.environ.get("ANDROID_NDK_HOME"),
                        help="Android NDK directory (default: ANDROID_NDK_HOME)")
    parser.add_argument("--secilc", default=os.environ.get("SECILC", "secilc"),
                        help="Policy compiler for both overlays (default: SECILC or secilc)")
    parser.add_argument("--compatibility", action="store_true",
                        help="Disable tested-device defaults for other GSI images")
    parser.add_argument("--ir", action=argparse.BooleanOptionalAction, default=None,
                        help="Include the IR HAL (default except in compatibility mode)")
    parser.add_argument("--xrz", action=argparse.BooleanOptionalAction, default=None,
                        help="Include XRZ v2 (default except in compatibility mode)")
    parser.add_argument("--experimental-phh-reduction", action=argparse.BooleanOptionalAction, default=None,
                        help="Remove 70 PHH root grants for the exact tested EvoX baseline; not hardening")
    parser.add_argument("--experimental-property-only-refresh", action=argparse.BooleanOptionalAction, default=None,
                        help="Test composer property refresh without the daemon global_mode write")
    parser.add_argument("--init-eink-bridge", action=argparse.BooleanOptionalAction, default=None,
                        help="Use the tested init bridge for Auto Refresh and Anti-Shake")
    parser.add_argument("--enforcing-migration", action=argparse.BooleanOptionalAction, default=None,
                        help="Migrate e-ink daemon and display helpers to enforcing domains")
    parser.add_argument("--policy-jobs", type=int, choices=(1, 2), default=2,
                        help="Concurrent policy compiler processes (default: 2)")
    parser.add_argument("--strict-verification", action="store_true",
                        help="Run the full policy checks after each overlay")
    parser.add_argument("--output-root", type=Path, default=ROOT / "build",
                        help="Directory for a new timestamped build (default: build/)")
    args = parser.parse_args()
    for name in ("ir", "xrz", "experimental_phh_reduction",
                 "experimental_property_only_refresh", "init_eink_bridge", "enforcing_migration"):
        if getattr(args, name) is None:
            setattr(args, name, not args.compatibility)
    if args.enforcing_migration and not args.init_eink_bridge:
        parser.error("The enforcing migration requires --init-eink-bridge")
    if args.init_eink_bridge and not all((args.ir, args.xrz, args.experimental_phh_reduction,
                                           args.experimental_property_only_refresh)):
        parser.error("The tested init bridge requires --ir, --xrz, --experimental-phh-reduction "
                     "and --experimental-property-only-refresh; use --compatibility to disable tested defaults")
    if args.built_apk is None:
        args.source_apk = True

    require_input(parser, args.gsi, "GSI image")
    if args.built_apk is not None:
        require_input(parser, args.built_apk, "built APK")
        apk_inputs = {"built_apk": args.built_apk.resolve()}
    else:
        apk_inputs = source_apk_inputs(parser)
    if args.ir or args.xrz or args.experimental_phh_reduction or args.init_eink_bridge:
        if args.vendor_image is None:
            parser.error("--vendor-image is required for --ir, --xrz or --experimental-phh-reduction")
        require_input(parser, args.vendor_image, "vendor image")
    if args.ir:
        if args.aosp_headers is None or not args.aosp_headers.is_dir():
            parser.error("--aosp-headers must name the Android 12 header directory for --ir")
        for header in ("hardware/consumerir.h", "hardware/hardware.h"):
            if not (args.aosp_headers / header).is_file():
                parser.error(f"Missing AOSP header: {args.aosp_headers / header}")
    if args.init_eink_bridge:
        if sha256(args.gsi) != GSI_SHA256 or sha256(args.vendor_image) != VENDOR_SHA256:
            parser.error("Tested bridge/migration defaults require the exact tested GSI and vendor; "
                         "use --compatibility for other images")
        if args.ndk is None:
            parser.error("--ndk or ANDROID_NDK_HOME is required for the tested bridge")
    output_root = args.output_root.resolve()
    for path in (args.gsi, args.built_apk, args.vendor_image,
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
    final_image = build_dir / "HiBreakPro-release.img"
    stage_directory = tempfile.TemporaryDirectory(prefix=".release-stages-", dir=build_dir)
    stage_dir = Path(stage_directory.name)
    working_image = stage_dir / "HiBreakPro-release-working.img"
    parallel_commands = [["bash", str(ROOT / "tools/build/build-daemon.sh"), str(daemon)]]
    if args.enforcing_migration:
        parallel_commands[0].append("--enforcing-migration-candidate")
    elif args.experimental_property_only_refresh:
        parallel_commands[0].append("--experimental-property-only-refresh")
        if args.init_eink_bridge:
            parallel_commands[0].append("--experimental-init-eink-bridge")
    if args.source_apk:
        parallel_commands.append(
            ["bash", str(ROOT / "tools/build/build-source-apk.sh"), str(apk)])
    hal = build_dir / "consumerir.hxd-release.so"
    if args.ir:
        parallel_commands.append(["bash", str(ROOT / "tools/build/build-ir-hal.sh"), str(hal)])
    if args.experimental_phh_reduction:
        print("WARNING: experimental PHH grant reduction requested; root domain remains permissive.")

    input_files = {"gsi": args.gsi.resolve(), **apk_inputs}
    if args.vendor_image:
        input_files["vendor_image"] = args.vendor_image.resolve()
    if args.ir:
        for header in ("hardware/consumerir.h", "hardware/hardware.h"):
            path = args.aosp_headers / header
            input_files[f"aosp_header:{header}"] = path
    manifest = {
        "schema_version": 2,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "options": {
            "ir": args.ir, "xrz_v2": args.xrz, "release": True,
            "source_apk": args.source_apk, "reuse_built_apk": args.built_apk is not None,
            "experimental_property_only_refresh": args.experimental_property_only_refresh,
            "experimental_phh_reduction": args.experimental_phh_reduction,
            "init_eink_bridge": args.init_eink_bridge,
            "enforcing_eink_and_display": args.enforcing_migration,
            "policy_jobs": args.policy_jobs,
            "strict_verification": args.strict_verification,
            "verification_mode": (
                "combined" if not args.strict_verification and all((
                    args.ir, args.xrz, args.experimental_phh_reduction,
                    args.init_eink_bridge, args.enforcing_migration,
                )) else "per-stage"
            ),
        },
        "inputs": {
            name: {"path": str(path), "sha256": sha256(path)}
            for name, path in input_files.items()
        },
        "outputs": {},
        "stages": [],
        "final_image": str(final_image),
    }
    if args.source_apk:
        manifest["options"]["source_apk"] = True
    if args.experimental_property_only_refresh:
        manifest["options"]["experimental_property_only_refresh"] = True
    if args.init_eink_bridge:
        manifest["options"]["init_eink_bridge"] = True
    if args.enforcing_migration:
        manifest["options"]["enforcing_eink_and_display"] = True
    if args.experimental_phh_reduction:
        manifest["options"]["experimental_phh_reduction"] = True
        reduction_tool = ROOT / "tools/image/add-phh-reduction-to-gsi.py"
        manifest["inputs"]["phh_reduction_tool"] = {
            "path": str(reduction_tool), "sha256": sha256(reduction_tool),
        }
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
        for command in parallel_commands:
            print(f"Running: {Path(command[1]).name}", flush=True)
        with ThreadPoolExecutor(max_workers=len(parallel_commands)) as executor:
            futures = [
                executor.submit(subprocess.run, command, cwd=ROOT,
                                env=child_environment, check=True)
                for command in parallel_commands
            ]
            for future in futures:
                future.result()
        release_pipeline.build(
            args.gsi.resolve(), working_image, apk, daemon,
            args.vendor_image.resolve() if args.vendor_image else None,
            hal if args.ir else None, args.secilc,
            ir=args.ir, xrz=args.xrz, reduction=args.experimental_phh_reduction,
            bridge=args.init_eink_bridge, enforcing=args.enforcing_migration,
            parallel_compile=args.policy_jobs > 1,
            strict_verification=args.strict_verification,
            report=manifest["stages"],
        )
        os.link(working_image, final_image)
        working_image.unlink()
        outputs = [apk, daemon]
        if args.ir:
            outputs.append(hal)
        outputs.append(final_image)
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
    finally:
        stage_directory.cleanup()

    print(f"Final image: {final_image}")
    print(f"Manifest: {manifest_path}")
    print("No device was accessed or flashed.")


if __name__ == "__main__":
    main()
