#!/usr/bin/env python3
"""Build an opt-in enforcing e-ink daemon test image from the tested bridge image."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.hibreak import image

SPEC = importlib.util.spec_from_file_location("eink_migration", ROOT / "tools/check-eink-migration.py")
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)

SOURCE_SHA256 = "5844ef262b47d04cd3df990b3e97e71567a940ff85f8322348a6ce3ee722cdca"
DISPLAY = ROOT / "tools/display"
EXEC_PATH = "system/bin/a9_eink_server"
EXEC_CONTEXT = "u:object_r:hibreak_eink_exec:s0"
INIT_PATH = "system/etc/init/a9_eink_gsi.rc"
PROPERTY_CONTEXTS = f"{image.POLICY}/plat_property_contexts"
FILE_CONTEXTS = f"{image.POLICY}/plat_file_contexts"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_file_contexts(path):
    text = path.read_text()
    if any(line.split("#", 1)[0].split()[:1] == ["/system/bin/a9_eink_server"]
           for line in text.splitlines()):
        raise ValueError("An exact daemon executable file context already exists")
    path.write_text(text.rstrip("\n") + f"\n/system/bin/a9_eink_server {EXEC_CONTEXT}\n")


def policy_digest(inputs, vendor, work):
    digest = hashlib.sha256()
    for path in inputs:
        digest.update(path.read_bytes())
    value = digest.hexdigest()
    vendor_digest = image.extract(
        vendor, "/etc/selinux/precompiled_sepolicy.plat_sepolicy_and_mapping.sha256",
        work / "vendor-policy-digest",
    ).read_text().strip()
    if not re.fullmatch(r"[0-9a-fA-F]{64}", vendor_digest) or vendor_digest.lower() == value:
        raise ValueError("Invalid or unchanged vendor precompiled policy digest")
    path = work / "migration-policy-digest"
    path.write_text(value + "\n")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--vendor-image", type=Path, required=True)
    parser.add_argument("--ndk", type=Path, required=True)
    parser.add_argument("--secilc", default="secilc")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    for tool in ("debugfs", "e2fsck", "resize2fs", "dumpe2fs", "cp", args.secilc):
        if not shutil.which(tool):
            parser.error(f"Missing dependency: {tool}")
    for path in (args.source, args.vendor_image):
        if not path.is_file() or path.stat().st_size == 0:
            parser.error(f"Missing input: {path}")
    for path in (args.source, args.vendor_image, args.output, args.ndk, ROOT, Path(tempfile.gettempdir())):
        if any(char in str(path) for char in ('"', "\\", "\n", "\r")):
            parser.error(f"Unsupported path characters: {path}")
    manifest_path = args.output.with_name(args.output.name + ".manifest.json")
    if os.path.lexists(args.output) or os.path.lexists(manifest_path):
        parser.error("Refusing to overwrite image or manifest")
    if sha256(args.source) != SOURCE_SHA256:
        parser.error("Migration requires the exact user-tested init bridge image")
    with tempfile.TemporaryDirectory(prefix="hibreak-eink-migration-") as directory:
        work = Path(directory)
        platform, properties, inputs = migration.validate(
            args.source, args.vendor_image, work, args.secilc, True, True,
        )
        contexts = work / "contexts"
        prepare_file_contexts(contexts)
        digest = policy_digest(inputs, args.vendor_image, work)
        for path in (EXEC_PATH, INIT_PATH):
            if not image.image_exists(args.source, path):
                raise ValueError(f"Missing existing daemon component: {path}")
        control_rc = "system/etc/init/hibreak-eink-control.rc"
        if image.image_exists(args.source, control_rc):
            raise ValueError("Candidate control init script already present")
        if args.check_only:
            print("Migration preflight passed; no image written.")
            return
        daemon = work / "a9_eink_server"
        environment = os.environ.copy()
        environment["ANDROID_NDK_HOME"] = str(args.ndk.resolve())
        subprocess.run(["bash", str(ROOT / "tools/build-daemon.sh"), str(daemon),
                        "--enforcing-migration-candidate"], env=environment, check=True)
        installed = False
        manifest_created = False
        try:
            image.copy_and_grow(args.source, args.output, 32 * 1024 * 1024)
            installed = True
            for file, dest, mode, context in (
                (platform, f"{image.POLICY}/plat_sepolicy.cil", "0100644", "u:object_r:system_file:s0"),
                (properties, PROPERTY_CONTEXTS, "0100644", "u:object_r:system_file:s0"),
                (contexts, FILE_CONTEXTS, "0100644", "u:object_r:system_file:s0"),
                (digest, f"{image.POLICY}/plat_sepolicy_and_mapping.sha256", "0100644", "u:object_r:system_file:s0"),
                (DISPLAY / "hibreak-eink-control.rc", control_rc, "0100644", "u:object_r:system_file:s0"),
                (DISPLAY / "hibreak-eink-migration.rc", INIT_PATH, "0100644", "u:object_r:system_file:s0"),
                (daemon, EXEC_PATH, "0100755", EXEC_CONTEXT),
            ):
                image.install(args.output, file, dest, mode, context, work)
            image.shrink_and_check(args.output, strict_final=True)
            manifest = {
                "experimental_enforcing_eink_daemon": True,
                "source": {"path": str(args.source.resolve()), "sha256": SOURCE_SHA256},
                "vendor": {"path": str(args.vendor_image.resolve()), "sha256": sha256(args.vendor_image)},
                "daemon_sha256": sha256(daemon),
                "image": {"path": str(args.output.resolve()), "sha256": sha256(args.output)},
            }
            with manifest_path.open("x") as stream:
                manifest_created = True
                json.dump(manifest, stream, indent=2)
                stream.write("\n")
        except (OSError, ValueError, subprocess.CalledProcessError):
            if installed:
                args.output.unlink(missing_ok=True)
            if manifest_created:
                manifest_path.unlink(missing_ok=True)
            raise
    print(f"Experimental migration image: {args.output}")
    print(f"Manifest: {manifest_path}")
    print("No device was accessed or flashed; device validation is required.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            print(((error.stdout or b"") + (error.stderr or b"")).decode(errors="replace"), file=sys.stderr)
        raise SystemExit(str(error))
