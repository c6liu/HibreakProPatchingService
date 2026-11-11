"""Vendor-policy merge helpers shared by offline image overlays."""

import re
import subprocess
from pathlib import Path

from tools.hibreak import image


ROOT = Path(__file__).resolve().parents[2]
POLICY = image.POLICY


def neverallow_failures(result):
    if result.returncode == 0:
        return set()
    diagnostics = result.stderr.decode(errors="replace")
    failures = {failure.rstrip("\n") + "\n" for failure in re.findall(
        r"^neverallowx? check failed .*?(?=\nneverallowx? check failed |\nFailed to generate binary|\Z)",
        diagnostics, re.S | re.M,
    )}
    if not failures:
        raise ValueError(f"Policy compilation failed:\n{diagnostics}")
    return failures


def prepare_ir_policy(source, vendor, work, compiler, remote=False, hal=False,
                      diagnostics=False, allow_existing_ir=False):
    if remote and not diagnostics:
        raise ValueError("Remote app policy requires diagnostic service policy")
    if allow_existing_ir and (remote or hal or diagnostics):
        raise ValueError("Cannot add another IR overlay when allowing existing IR policy")
    if not image.image_exists(source, "system/bin/secilc"):
        raise ValueError("GSI has no /system/bin/secilc for boot-time policy recompilation")
    if image.image_exists(vendor, "/odm/etc/selinux/odm_sepolicy.cil"):
        raise ValueError("Vendor contains additional ODM policy; this overlay does not support it")
    version = image.extract(
        vendor, "/etc/selinux/plat_sepolicy_vers.txt", work / "version",
    ).read_text().strip()
    if not re.fullmatch(r"\d+\.\d+", version):
        raise ValueError(f"Invalid vendor policy version: {version!r}")
    platform = image.extract(source, f"{POLICY}/plat_sepolicy.cil", work / "plat.cil")
    text = platform.read_text()
    if not allow_existing_ir and ("hibreak_ir_capture" in text or "hibreak_ir_hal_file" in text):
        raise ValueError("IR policy already present; start from an image without this overlay")
    inputs = [platform]
    for label, directory, required in (
        ("plat", POLICY, True),
        ("ext", "system/system_ext/etc/selinux", False),
        ("product", "system/product/etc/selinux", False),
    ):
        if label != "plat":
            path = f"{directory}/{'system_ext' if label == 'ext' else label}_sepolicy.cil"
            if image.image_exists(source, path):
                inputs.append(image.extract(source, path, work / f"{label}.cil"))
        for suffix in (".cil", ".compat.cil"):
            path = f"{directory}/mapping/{version}{suffix}"
            if image.image_exists(source, path):
                inputs.append(image.extract(source, path, work / f"{label}-mapping{suffix}"))
            elif required and suffix == ".cil":
                raise ValueError(f"GSI has no mapping for stock vendor policy {version}")
    for name in ("plat_pub_versioned.cil", "vendor_sepolicy.cil"):
        inputs.append(image.extract(vendor, f"/etc/selinux/{name}", work / name))
    command = [compiler, "-m", "-M", "true", "-G", "-c", "30",
               *map(str, inputs), "-o", str(work / "validated.policy"),
               "-f", str(work / "validated.contexts")]
    baseline = neverallow_failures(subprocess.run(command, capture_output=True))
    extra = (ROOT / "tools/ir/hibreak-ir-capture.cil").read_text() if diagnostics else ""
    if remote:
        extra += "\n" + (ROOT / "tools/ir/hibreak-ir-remote.cil").read_text()
    if hal:
        extra += "\n" + (ROOT / "tools/ir/hibreak-ir-hal.cil").read_text()
    platform.write_text(text + "\n" + extra)
    modified = neverallow_failures(subprocess.run(command, capture_output=True))
    added = modified - baseline
    if added:
        raise ValueError("IR overlay adds neverallow violations:\n" + "\n".join(sorted(added)))
    if baseline:
        print(f"WARNING: base GSI/vendor merge has {len(baseline)} existing neverallow/neverallowx conflicts.")
        print("The requested policy changes add none; compiling with Android init's runtime -N option.")
        image.run(*command, "-N")
    contexts = image.extract(source, f"{POLICY}/plat_file_contexts", work / "contexts")
    if diagnostics:
        contexts.write_text(
            contexts.read_text() + "\n" +
            (ROOT / "tools/ir/hibreak-ir-file-contexts").read_text(),
        )
    if hal:
        contexts.write_text(
            contexts.read_text() +
            "\n/system/lib64/consumerir\\.hxd\\.so u:object_r:hibreak_ir_hal_file:s0\n",
        )
    return platform, contexts, inputs
