"""Verified ext4 image operations shared by offline overlay tools."""

import subprocess


POLICY = "system/etc/selinux"


def run(*args):
    return subprocess.run(args, check=True, capture_output=True)


def image_exists(image, path):
    return b"Inode:" in run("debugfs", "-R", f"stat {path}", str(image)).stdout


def extract(image, path, destination):
    if not image_exists(image, path):
        raise ValueError(f"Missing image input: {image}:{path}")
    run("debugfs", "-R", f'dump {path} "{destination}"', str(image))
    if not destination.is_file():
        raise ValueError(f"debugfs did not extract {path}")
    return destination


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
    if (context not in stat or f"Mode:  {mode[-4:]}" not in stat
            or "User:     0   Group:     0" not in stat):
        raise ValueError(f"Image metadata verification failed: {destination}\n{stat}")


def fsck(image, *args):
    result = subprocess.run(["e2fsck", *args, str(image)], capture_output=True)
    if result.returncode not in (0, 1):
        raise ValueError(result.stdout.decode() + result.stderr.decode())


def install_app(image, apk, directory, filename, work):
    ensure_directory(image, directory, "u:object_r:system_file:s0", work)
    install(image, apk, f"{directory}/{filename}", "0100644", "u:object_r:system_file:s0", work)


def ensure_directory(image, path, context, work):
    if not image_exists(image, path):
        run("debugfs", "-w", "-R", f"mkdir {path}", str(image))
    for field, value in (("mode", "040755"), ("uid", "0"), ("gid", "0")):
        run("debugfs", "-w", "-R", f"sif {path} {field} {value}", str(image))
    label_file = work / "directory-label"
    label_file.write_bytes(context.encode() + b"\0")
    run("debugfs", "-w", "-R", f'ea_set -f "{label_file}" {path} security.selinux', str(image))


def copy_and_grow(source, output, headroom):
    import os

    fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    os.close(fd)
    try:
        run("cp", "--reflink=auto", str(source), str(output))
        os.truncate(output, output.stat().st_size + headroom)
        fsck(output, "-fy")
        run("resize2fs", str(output))
        fsck(output, "-fy", "-E", "unshare_blocks")
    except BaseException:
        output.unlink(missing_ok=True)
        raise


def shrink_and_check(image, strict_final=False):
    import os
    import re

    fsck(image, "-fy")
    run("resize2fs", "-M", str(image))
    header = run("dumpe2fs", "-h", str(image)).stdout.decode()
    blocks = re.search(r"^Block count:\s+(\d+)$", header, re.M)
    size = re.search(r"^Block size:\s+(\d+)$", header, re.M)
    if not blocks or not size:
        raise ValueError("Cannot determine minimized image size")
    os.truncate(image, int(blocks[1]) * int(size[1]))
    if strict_final:
        result = subprocess.run(["e2fsck", "-fn", str(image)], capture_output=True)
        if result.returncode:
            raise ValueError(
                "Final filesystem check failed:\n" +
                (result.stdout + result.stderr).decode(errors="replace")
            )
        return
    fsck(image, "-fn")
