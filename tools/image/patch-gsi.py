#!/usr/bin/env python3
"""Patch display/AOD support into a raw ext4 TrebleDroid GSI offline."""

import base64
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.hibreak import image


def usage():
    return (
        "Usage: patch-gsi.py <raw-ext4-gsi.img> <output.img> <standalone.apk> "
        "<daemon> [adbkey.pub] [--release] [--root]"
    )


def parse_arguments(arguments):
    if len(arguments) < 4 or len(arguments) > 7:
        raise ValueError(usage())
    source, output, apk, daemon = map(Path, arguments[:4])
    key = None
    release = False
    keep_root = False
    for argument in arguments[4:]:
        if argument == "--release":
            if release:
                raise ValueError("Duplicate option: --release")
            release = True
        elif argument == "--root":
            if keep_root:
                raise ValueError("Duplicate option: --root")
            keep_root = True
        elif key is None:
            key = Path(argument)
        else:
            raise ValueError(f"Unexpected argument: {argument}")
    if release and key is not None:
        raise ValueError("--release cannot be combined with an ADB public key")
    return source, output, apk, daemon, key, release, keep_root


def validate_adb_key(path):
    lines = path.read_text().splitlines()
    if len(lines) != 1 or not lines[0].split():
        raise ValueError("Expected a single ADB public key, not a private key or key bundle")
    try:
        data = base64.b64decode(lines[0].split()[0], validate=True)
    except ValueError as error:
        raise ValueError("Invalid ADB public key encoding") from error
    if len(data) != 524 or struct.unpack_from("<I", data)[0] != 64:
        raise ValueError("Expected an Android 2048-bit RSA adbkey.pub")


def validate_paths(paths):
    for path in paths:
        if any(character in str(path) for character in ('"', "\\", "\n", "\r")):
            raise ValueError(f"Unsupported character in path: {path}")


def exists(path, image_path):
    return image.image_exists(image_path, path)


def put(image_path, source, destination, mode, context, work):
    image.install(image_path, source, destination, mode, context, work)


def fsck_fix(image_path, *arguments):
    image.fsck(image_path, *arguments)


def read_image(image_path, path):
    return image.run("debugfs", "-R", f"cat {path}", str(image_path)).stdout.decode()


def prepare_release_files(display_rc, eink_rc, work):
    helper = ROOT / "tools/internal/prepare-release-init.py"
    image.run(
        sys.executable, str(helper), str(display_rc), str(eink_rc), str(work),
    )
    return work / "hibreak-display-release.rc", work / "eink_gsi-release.rc"


def patch_image(source, output, apk, daemon, key, release, keep_root, finalize=True):
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gsi.", dir=build) as temp:
        work = Path(temp)
        context = work / "context"
        context.write_bytes(b"u:object_r:system_file:s0\0")
        adb_context = work / "adb-context"
        adb_context.write_bytes(b"u:object_r:adb_keys_file:s0\0")
        display_rc = ROOT / "tools/display/hibreak-display.rc"
        eink_rc = ROOT / "eink_daemon/etc/init/eink_gsi.rc"
        if not exists("system/etc/init/vndk.rc", source):
            raise ValueError("GSI has no system/etc/init/vndk.rc")
        vndk = image.extract(source, "system/etc/init/vndk.rc", work / "vndk.rc")
        if "u:r:phhsu_daemon:s0" not in vndk.read_text():
            raise ValueError(
                "Expected a raw ext4 TrebleDroid GSI providing phhsu_daemon in vndk.rc.\n"
                "Extract .xz first; sparse images need simg2img. EROFS is not supported."
            )
        if release:
            display_rc, eink_rc = prepare_release_files(display_rc, eink_rc, work)

        descriptor = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        os.close(descriptor)
        image.run("cp", "--reflink=auto", str(source), str(output))
        os.truncate(output, output.stat().st_size + 256 * 1024 * 1024)
        fsck_fix(output, "-fy")
        image.run("resize2fs", str(output))
        fsck_fix(output, "-fy", "-E", "unshare_blocks")

        try:
            for prop in (
                "system/build.prop",
                "system/system_ext/etc/build.prop",
                "system/product/etc/build.prop",
            ):
                if not exists(prop, output):
                    continue
                prop_file = work / "build.prop"
                image.extract(output, prop, prop_file)
                image.run(
                    sys.executable, str(ROOT / "tools/internal/update-build-prop.py"),
                    str(prop_file), prop,
                )
                put(output, prop_file, prop, "0100644", "u:object_r:system_file:s0", work)

            if exists("system/xbin/su", output) and not keep_root:
                image.run("debugfs", "-w", "-R", "rm system/xbin/su", str(output))
            if exists("system/bin/hibreak-enable-adb.sh", output):
                image.run("debugfs", "-w", "-R", "rm system/bin/hibreak-enable-adb.sh", str(output))

            legacy_app_directory = "system/priv-app/HiBreakEink"
            if exists(legacy_app_directory, output):
                legacy_apk = f"{legacy_app_directory}/HiBreakEink.apk"
                if exists(legacy_apk, output):
                    image.run("debugfs", "-w", "-R", f"rm {legacy_apk}", str(output))
                image.run("debugfs", "-w", "-R", f"rmdir {legacy_app_directory}", str(output))
                if exists(legacy_app_directory, output):
                    raise ValueError(f"Could not remove legacy APK directory: {legacy_app_directory}")

            if not exists("system/priv-app/EinkSettings", output):
                image.run("debugfs", "-w", "-R", "mkdir system/priv-app/EinkSettings", str(output))
            image.ensure_directory(
                output, "system/priv-app/EinkSettings", "u:object_r:system_file:s0", work,
            )
            if exists("system/etc/init/eink_daemon.rc", output):
                raise ValueError("Conflicting AOSP daemon init file exists; start from the unmodified GSI.")
            put(output, apk, "system/priv-app/EinkSettings/HiBreakEink.apk",
                "0100644", "u:object_r:system_file:s0", work)
            put(output, daemon, "system/bin/eink_server",
                "0100755", "u:object_r:system_file:s0", work)
            put(output, eink_rc, "system/etc/init/eink_gsi.rc",
                "0100644", "u:object_r:system_file:s0", work)
            put(
                output, ROOT / "eink_settings/privapp-permissions-accessibility.xml",
                "system/etc/permissions/privapp-permissions-hibreak-eink.xml",
                "0100644", "u:object_r:system_file:s0", work,
            )
            put(output, display_rc, "system/etc/init/hibreak-display.rc",
                "0100644", "u:object_r:system_file:s0", work)
            for name in ("hibreak-disable-hwc", "hibreak-wake-cycle", "hibreak-aod"):
                put(
                    output, ROOT / f"tools/display/{name}.sh", f"system/bin/{name}.sh",
                    "0100755", "u:object_r:system_file:s0", work,
                )

            if key is not None:
                put(output, key, "adb_keys", "0100644", "u:object_r:adb_keys_file:s0", work)
            validate_patched_image(output, key, release, keep_root)
            if not finalize:
                return
            fsck_fix(output, "-fy")
            image.run("resize2fs", "-M", str(output))
            header = image.run("dumpe2fs", "-h", str(output)).stdout.decode()
            blocks = re.search(r"^Block count:\s+(\d+)$", header, re.M)
            block_size = re.search(r"^Block size:\s+(\d+)$", header, re.M)
            if not blocks or not block_size:
                raise ValueError("Unable to determine image size")
            os.truncate(output, int(blocks[1]) * int(block_size[1]))
            final_check = subprocess.run(["e2fsck", "-fn", str(output)], capture_output=True)
            if final_check.returncode:
                raise ValueError(
                    (final_check.stdout + final_check.stderr).decode(errors="replace")
                )
            sys.stdout.write((image.run("sha256sum", str(output)).stdout).decode())
            print("Verified image ready. Nothing has been flashed.")
        except BaseException:
            print(f"Incomplete output image left at {output}", file=sys.stderr)
            raise


def validate_patched_image(image_path, key, release, keep_root):
    system_properties = read_image(image_path, "system/build.prop").splitlines()
    if "persist.sys.usb.config=mtp" not in system_properties:
        raise ValueError("Image does not default to MTP-only USB configuration")
    gamma_property = "sys.brightness.disable_gamma_conversion"
    if f"{gamma_property}=true" not in system_properties:
        raise ValueError("Image does not disable native brightness slider gamma conversion")
    display = read_image(image_path, "system/etc/init/hibreak-display.rc")
    if re.search(r"setprop (?:persist\.sys\.usb\.config|sys\.usb\.config)|hibreak_enable_adb", display):
        raise ValueError("Image init script overrides saved USB debugging state")
    if exists("system/bin/hibreak-enable-adb.sh", image_path):
        raise ValueError("Image still contains the USB ADB enable script")
    for prop in ("system/system_ext/etc/build.prop", "system/product/etc/build.prop"):
        if exists(prop, image_path):
            for line in read_image(image_path, prop).splitlines():
                if line.startswith("persist.sys.usb.config=") and line != "persist.sys.usb.config=mtp":
                    raise ValueError(f"{prop} overrides the MTP-only USB configuration")
                if line.startswith(gamma_property + "=") and line != f"{gamma_property}=true":
                    raise ValueError(f"{prop} overrides native brightness slider gamma conversion")
    for prop in ("system/build.prop", "system/system_ext/etc/build.prop",
                 "system/product/etc/build.prop"):
        if exists(prop, image_path) and "ro.adb.secure=0" in read_image(image_path, prop).splitlines():
            raise ValueError(f"{prop} disables ADB authorization")
    if keep_root:
        print("Root kept: /system/xbin/su is available to ADB shell (--root).")
    elif exists("system/xbin/su", image_path):
        raise ValueError("Image still contains /system/xbin/su")
    if release:
        print("Release mode: saved USB debugging state preserved; diagnostic hooks disabled.")
        for path in ("system/etc/init/hibreak-display.rc", "system/etc/init/eink_gsi.rc"):
            if "debug.hibreak" in read_image(image_path, path):
                raise ValueError(f"Release image retains a diagnostic hook in {path}")
    if key is not None and not exists("adb_keys", image_path):
        raise ValueError("Image is missing the requested ADB public key")


def main(arguments):
    source, output, apk, daemon, key, release, keep_root = parse_arguments(arguments)
    for tool in ("debugfs", "e2fsck", "resize2fs", "dumpe2fs", "sha256sum", "python3"):
        if not shutil.which(tool):
            raise ValueError(f"Missing dependency: {tool}")
    for path in (source, apk, daemon):
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Missing input: {path}")
    if key is not None:
        if not key.is_file() or key.stat().st_size == 0:
            raise ValueError(f"Missing input: {key}")
        validate_adb_key(key)
    if os.path.lexists(output):
        raise ValueError(f"Refusing to overwrite: {output}")
    validate_paths((source, output, apk, daemon, key, ROOT, Path(tempfile.gettempdir())))
    patch_image(source, output, apk, daemon, key, release, keep_root)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            sys.stderr.write((error.stdout or b"").decode(errors="replace"))
            sys.stderr.write((error.stderr or b"").decode(errors="replace"))
        raise SystemExit(str(error))
