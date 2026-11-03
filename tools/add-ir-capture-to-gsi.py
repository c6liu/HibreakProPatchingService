#!/usr/bin/env python3
"""Add an opt-in IR capture service to an ext4 GSI; never flash or access ADB."""

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
POLICY = "system/etc/selinux"


def run(*args):
    return subprocess.run(args, check=True, capture_output=True)


def image_exists(image, path):
    result = run("debugfs", "-R", f"stat {path}", str(image))
    return b"Inode:" in result.stdout


def extract(image, path, destination):
    if not image_exists(image, path):
        raise ValueError(f"Missing image input: {image}:{path}")
    run("debugfs", "-R", f'dump {path} "{destination}"', str(image))
    if not destination.is_file():
        raise ValueError(f"debugfs did not extract {path}")
    return destination


def neverallow_failures(result):
    if result.returncode == 0:
        return set()
    diagnostics = result.stderr.decode(errors="replace")
    failures = set(re.findall(
        r"neverallow check failed .*?(?=\nneverallow check failed |\nFailed to generate binary|\Z)",
        diagnostics, re.S,
    ))
    if not failures:
        raise ValueError(f"Policy compilation failed:\n{diagnostics}")
    return failures


def prepare_policy(source, vendor, work, compiler):
    if not image_exists(source, "system/bin/secilc"):
        raise ValueError("GSI has no /system/bin/secilc for boot-time policy recompilation")
    if image_exists(vendor, "/odm/etc/selinux/odm_sepolicy.cil"):
        raise ValueError("Vendor contains additional ODM policy; this overlay does not support it")
    version = extract(vendor, "/etc/selinux/plat_sepolicy_vers.txt", work / "version").read_text().strip()
    if not re.fullmatch(r"\d+\.\d+", version):
        raise ValueError(f"Invalid vendor policy version: {version!r}")
    platform = extract(source, f"{POLICY}/plat_sepolicy.cil", work / "plat.cil")
    text = platform.read_text()
    if "hibreak_ir_capture" in text:
        raise ValueError("IR policy already present; start from an image without this overlay")
    inputs = [platform]
    for label, directory, required in (
        ("plat", POLICY, True),
        ("ext", "system/system_ext/etc/selinux", False),
        ("product", "system/product/etc/selinux", False),
    ):
        if label != "plat":
            path = f"{directory}/{'system_ext' if label == 'ext' else label}_sepolicy.cil"
            if image_exists(source, path):
                inputs.append(extract(source, path, work / f"{label}.cil"))
        for suffix in (".cil", ".compat.cil"):
            path = f"{directory}/mapping/{version}{suffix}"
            if image_exists(source, path):
                inputs.append(extract(source, path, work / f"{label}-mapping{suffix}"))
            elif required and suffix == ".cil":
                raise ValueError(f"GSI has no mapping for stock vendor policy {version}")
    for name in ("plat_pub_versioned.cil", "vendor_sepolicy.cil"):
        inputs.append(extract(vendor, f"/etc/selinux/{name}", work / name))
    command = [compiler, "-m", "-M", "true", "-G", "-c", "30",
               *map(str, inputs), "-o", str(work / "validated.policy"),
               "-f", str(work / "validated.contexts")]
    baseline = neverallow_failures(subprocess.run(command, capture_output=True))
    platform.write_text(text + "\n" + (ROOT / "tools/ir/hibreak-ir-capture.cil").read_text())
    modified = neverallow_failures(subprocess.run(command, capture_output=True))
    added = modified - baseline
    if added:
        raise ValueError("IR overlay adds neverallow violations:\n" + "\n".join(sorted(added)))
    if baseline:
        print(f"WARNING: base GSI/vendor merge has {len(baseline)} existing neverallow conflicts.")
        print("IR overlay adds none; compiling with Android init's runtime -N option.")
        run(*command, "-N")
    contexts = extract(source, f"{POLICY}/plat_file_contexts", work / "contexts")
    contexts.write_text(contexts.read_text() + "\n" + (ROOT / "tools/ir/hibreak-ir-file-contexts").read_text())
    return platform, contexts, inputs


def install(image, source, destination, mode, context, work):
    if image_exists(image, destination):
        run("debugfs", "-w", "-R", f"rm {destination}", str(image))
    run("debugfs", "-w", "-R", f'write "{source}" {destination}', str(image))
    for field, value in (("mode", mode), ("uid", "0"), ("gid", "0")):
        run("debugfs", "-w", "-R", f"sif {destination} {field} {value}", str(image))
    label = work / "label"
    label.write_bytes(context.encode() + b"\0")
    run("debugfs", "-w", "-R", f'ea_set -f "{label}" {destination} security.selinux', str(image))
    check = work / "check"
    check.unlink(missing_ok=True)
    extract(image, destination, check)
    if source.read_bytes() != check.read_bytes():
        raise ValueError(f"Image verification failed: {destination}")
    stat = run("debugfs", "-R", f"stat {destination}", str(image)).stdout.decode()
    if context not in stat or f"Mode:  {mode[-4:]}" not in stat or "User:     0   Group:     0" not in stat:
        raise ValueError(f"Image metadata verification failed: {destination}\n{stat}")


def fsck(image, *args):
    result = subprocess.run(["e2fsck", *args, str(image)], capture_output=True)
    if result.returncode not in (0, 1):
        raise ValueError(result.stdout.decode() + result.stderr.decode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Raw ext4 GSI, optionally already display-patched")
    parser.add_argument("output", type=Path, help="New image; never overwritten")
    parser.add_argument("binary", type=Path, help="NDK-built arm64 hxd-learn")
    parser.add_argument("--vendor-image", required=True, type=Path, help="Matching stock vendor ext4 image, read-only")
    parser.add_argument("--secilc", default="secilc", help="Host CIL compiler")
    parser.add_argument("--check-only", action="store_true", help="Validate merged policy without producing an image")
    args = parser.parse_args()
    for tool in ("debugfs", "e2fsck", "resize2fs", "dumpe2fs", "cp", args.secilc):
        if not shutil.which(tool):
            parser.error(f"Missing dependency: {tool}")
    for path in (args.source, args.output, args.binary, args.vendor_image, ROOT, Path(tempfile.gettempdir())):
        if any(char in str(path) for char in ('"', "\\", "\n", "\r")):
            parser.error(f"Unsupported path characters: {path}")
    for path in (args.source, args.binary, args.vendor_image):
        if not path.is_file() or path.stat().st_size == 0:
            parser.error(f"Missing input: {path}")
    if os.path.lexists(args.output):
        parser.error(f"Refusing to overwrite: {args.output}")
    binary = args.binary.read_bytes()
    if len(binary) < 20 or binary[:5] != b"\x7fELF\x02" or binary[18:20] != b"\xb7\x00":
        parser.error("Expected an arm64 ELF capture binary")
    if len(binary) < 64 or binary[5] != 1:
        parser.error("Expected a complete little-endian ELF header")
    phoff = int.from_bytes(binary[32:40], "little")
    phsize = int.from_bytes(binary[54:56], "little")
    phnum = int.from_bytes(binary[56:58], "little")
    if phsize < 56 or not phnum or phoff + phsize * phnum > len(binary):
        parser.error("Invalid ELF program headers")
    if any(int.from_bytes(binary[off:off + 4], "little") == 3
           for off in range(phoff, phoff + phsize * phnum, phsize)):
        parser.error("Service requires a static executable; rebuild with tools/build-ir-tool.sh")
    with tempfile.TemporaryDirectory(prefix="hibreak-ir-") as directory:
        work = Path(directory)
        platform, contexts, inputs = prepare_policy(args.source, args.vendor_image, work, args.secilc)
        print("Merged GSI + stock vendor IR policy compiled; no new neverallow conflicts.")
        if args.check_only:
            return
        # This is a cache-buster for our overlay, not an AOSP build-system hash.
        digest = hashlib.sha256()
        for path in inputs:
            digest.update(path.read_bytes())
        digest_file = work / "policy-digest"
        digest_file.write_text(digest.hexdigest() + "\n")
        # Reserve the output first; cp writes only to the file just created here.
        fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        os.close(fd)
        try:
            run("cp", "--reflink=auto", str(args.source), str(args.output))
            os.truncate(args.output, args.output.stat().st_size + 32 * 1024 * 1024)
            fsck(args.output, "-fy")
            run("resize2fs", str(args.output))
            fsck(args.output, "-fy", "-E", "unshare_blocks")
            for source, dest, mode, label in (
                (platform, f"{POLICY}/plat_sepolicy.cil", "0100644", "system_file"),
                (contexts, f"{POLICY}/plat_file_contexts", "0100644", "system_file"),
                (digest_file, f"{POLICY}/plat_sepolicy_and_mapping.sha256", "0100644", "system_file"),
                (args.binary, "system/bin/hxd-learn", "0100755", "hibreak_ir_capture_exec"),
                (ROOT / "tools/ir/hibreak-ir-capture.rc", "system/etc/init/hibreak-ir-capture.rc", "0100644", "system_file"),
            ):
                install(args.output, source, dest, mode, f"u:object_r:{label}:s0", work)
            fsck(args.output, "-fy")
            run("resize2fs", "-M", str(args.output))
            header = run("dumpe2fs", "-h", str(args.output)).stdout.decode()
            blocks = re.search(r"^Block count:\s+(\d+)$", header, re.M)
            size = re.search(r"^Block size:\s+(\d+)$", header, re.M)
            if not blocks or not size:
                raise ValueError("Cannot determine minimized image size")
            os.truncate(args.output, int(blocks[1]) * int(size[1]))
            fsck(args.output, "-fn")
        except BaseException:
            args.output.unlink()
            raise
    print(f"Verified IR capture test image: {args.output}")
    print("No flashing, ADB access, learning, or IR transmission was performed.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stdout.decode(errors="replace") + error.stderr.decode(errors="replace"), file=sys.stderr)
        raise SystemExit(str(error))
