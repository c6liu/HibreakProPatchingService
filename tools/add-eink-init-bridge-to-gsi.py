#!/usr/bin/env python3
"""Build an opt-in init e-ink bridge image from the tested full-overlay image."""

import argparse
import hashlib
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
from tools.hibreak.policy import neverallow_failures, prepare_ir_policy
from tools.hibreak.properties import effective_permissions, parse_contexts, resolve_context
from tools.hibreak.tested_stages import validate_rebuild

SOURCE_SHA256 = "e04bb8354ffcf2a999945bc83fe1d834caa1c131bfe3574353d1939134ee70e2"
LABEL = "u:object_r:hibreak_eink_bridge_prop:s0"
REQUESTS = ("sys.hibreak.eink_bridge.auto_refresh", "sys.hibreak.eink_bridge.anti_flicker")
NODES = ("/eink_debug/clean_a2", "/eink_debug/anti_flicker")
DISPLAY = ROOT / "tools/display"
PLAT_CONTEXTS = f"{image.POLICY}/plat_property_contexts"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_contexts(platform, other):
    entries = parse_contexts(PLAT_CONTEXTS, platform)
    for source, text in other:
        entries.extend(parse_contexts(source, text))
    additions = (DISPLAY / "hibreak-init-eink-bridge-property-contexts").read_text()
    requests = parse_contexts("bridge", additions)
    if len(requests) != 2 or {entry.name for entry in requests} != set(REQUESTS):
        raise ValueError("Bridge must define exactly two request properties")
    for entry in requests:
        if (entry.label, entry.match, entry.value_type) != (LABEL, "exact", ("enum", "0", "1")):
            raise ValueError(f"Invalid bridge property context: {entry.name}")
        if any(old.name == entry.name and old.match == "exact" for old in entries):
            raise ValueError(f"Property already has an exact context: {entry.name}")
        if resolve_context(entry.name, [*entries, *requests]) != entry:
            raise ValueError(f"Bridge property does not resolve uniquely: {entry.name}")
    return platform.rstrip("\n") + "\n\n# experimental init e-ink bridge\n" + additions


def prepare_bridge(source, vendor, work, compiler):
    from setools import SELinuxPolicy, TERuleQuery
    from setools.exception import RuleNotConditional

    platform, _, inputs = prepare_ir_policy(source, vendor, work, compiler, allow_existing_ir=True)
    original = platform.read_text()
    if "hibreak_eink_bridge_" in original:
        raise ValueError("Init e-ink bridge already present")
    baseline_policy = SELinuxPolicy(str(work / "validated.policy"))
    for node in NODES:
        matching = [rule for rule in baseline_policy.genfscons()
                    if rule.fs == "debugfs" and node.startswith(str(rule.path).rstrip("/") + "/")]
        matching += [rule for rule in baseline_policy.genfscons()
                     if rule.fs == "debugfs" and str(rule.path) == node]
        if not matching or str(max(matching, key=lambda rule: len(str(rule.path))).context.type_) != "debugfs":
            raise ValueError(f"Expected generic debugfs baseline for {node}")
    old_permissions = effective_permissions(baseline_policy, "debugfs", TERuleQuery, RuleNotConditional)
    old_file = {item for item in old_permissions if item[1] == "file"}
    contexts = image.extract(source, PLAT_CONTEXTS, work / "bridge-property-contexts")
    others = []
    for label, img, path, required in (
        ("system_ext", source, "system/system_ext/etc/selinux/system_ext_property_contexts", False),
        ("product", source, "system/product/etc/selinux/product_property_contexts", False),
        ("vendor", vendor, "/etc/selinux/vendor_property_contexts", True),
        ("odm", vendor, "/odm/etc/selinux/odm_property_contexts", False),
    ):
        if image.image_exists(img, path):
            others.append((label, image.extract(img, path, work / f"{label}-contexts").read_text()))
        elif required:
            raise ValueError(f"Missing {label} property contexts")
    contexts.write_text(add_contexts(contexts.read_text(), others))
    command = [compiler, "-m", "-M", "true", "-G", "-c", "30", *map(str, inputs),
               "-o", str(work / "bridge.policy"), "-f", str(work / "bridge.contexts")]
    baseline = neverallow_failures(subprocess.run(command, capture_output=True))
    platform.write_text(original.rstrip("\n") + "\n\n" +
                        (DISPLAY / "hibreak-init-eink-bridge.cil").read_text())
    changed = neverallow_failures(subprocess.run(command, capture_output=True))
    if changed - baseline:
        raise ValueError("Bridge changes neverallow diagnostics:\n" + "\n".join(sorted(changed - baseline)))
    image.run(*command, "-N")
    policy = SELinuxPolicy(str(work / "bridge.policy"))
    actual = effective_permissions(policy, "hibreak_eink_bridge_debugfs", TERuleQuery, RuleNotConditional)
    actual_file = {item for item in actual if item[1] == "file"}
    expected = {("init", "file", "open"), ("init", "file", "write")}
    if old_file - actual_file or actual_file - old_file != expected:
        raise ValueError(f"Unexpected debugfs file permissions: lost={old_file - actual_file}, "
                         f"added={actual_file - old_file}")
    property_permissions = effective_permissions(policy, "hibreak_eink_bridge_prop",
                                                 TERuleQuery, RuleNotConditional)
    writers = {src for src, cls, perm in property_permissions
               if cls == "property_service" and perm == "set"}
    if writers != {"init", "phhsu_daemon"}:
        raise ValueError(f"Unexpected bridge property writers: {sorted(writers)}")
    for target, cls, perm in (("property_socket", "sock_file", "write"),
                              ("init", "unix_stream_socket", "connectto")):
        if not any(TERuleQuery(policy, ruletype=["allow"], source="phhsu_daemon",
                               target=target, tclass=[cls], perms=[perm]).results()):
            raise ValueError(f"Daemon lacks bridge property-service access: {target}:{cls} {perm}")
    for node in NODES:
        if not any(rule.fs == "debugfs" and str(rule.path) == node and
                   str(rule.context.type_) == "hibreak_eink_bridge_debugfs"
                   for rule in policy.genfscons()):
            raise ValueError(f"Bridge node label missing: {node}")
    digest = hashlib.sha256()
    for path in inputs:
        digest.update(path.read_bytes())
    digest_file = work / "bridge-policy-digest"
    digest_file.write_text(digest.hexdigest() + "\n")
    vendor_digest = image.extract(vendor, "/etc/selinux/precompiled_sepolicy.plat_sepolicy_and_mapping.sha256",
                                  work / "vendor-policy-digest").read_text().strip()
    if not re.fullmatch(r"[0-9a-fA-F]{64}", vendor_digest) or vendor_digest.lower() == digest.hexdigest():
        raise ValueError("Invalid or unchanged vendor precompiled policy digest")
    print(f"Policy: {len(baseline)} baseline conflicts; no new diagnostic blocks.", flush=True)
    print("Init-only debugfs file permissions preserve baseline access.", flush=True)
    return platform, contexts, digest_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--vendor-image", type=Path, required=True)
    parser.add_argument("--ndk", type=Path, required=True)
    parser.add_argument("--secilc", default="secilc")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--rebuild-gsi", type=Path,
                        help="Verify critical stage inputs against the tested GSI rebuild")
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
    source_sha = sha256(args.source)
    if args.rebuild_gsi:
        validate_rebuild(args.source, args.vendor_image, args.rebuild_gsi, "base")
    elif source_sha != SOURCE_SHA256:
        parser.error("This experiment requires the exact tested IR/XRZ/PHH-reduced refresh-only image")
    with tempfile.TemporaryDirectory(prefix="hibreak-init-eink-") as directory:
        work = Path(directory)
        files = prepare_bridge(args.source, args.vendor_image, work, args.secilc)
        if args.check_only:
            print("Preflight passed; no image written.")
            return
        daemon = work / "a9_eink_server"
        environment = os.environ.copy()
        environment["ANDROID_NDK_HOME"] = str(args.ndk.resolve())
        subprocess.run(["bash", str(ROOT / "tools/build-daemon.sh"), str(daemon),
                        "--experimental-property-only-refresh", "--experimental-init-eink-bridge"],
                       env=environment, check=True)
        if image.image_exists(args.source, "system/etc/init/hibreak-init-eink-bridge.rc"):
            raise ValueError("Bridge init script already present")
        installed = False
        try:
            image.copy_and_grow(args.source, args.output, 32 * 1024 * 1024)
            installed = True
            for file, dest, mode in (
                (files[0], f"{image.POLICY}/plat_sepolicy.cil", "0100644"),
                (files[1], PLAT_CONTEXTS, "0100644"),
                (files[2], f"{image.POLICY}/plat_sepolicy_and_mapping.sha256", "0100644"),
                (DISPLAY / "hibreak-init-eink-bridge.rc", "system/etc/init/hibreak-init-eink-bridge.rc", "0100644"),
                (daemon, "system/bin/a9_eink_server", "0100755"),
            ):
                image.install(args.output, file, dest, mode, "u:object_r:system_file:s0", work)
            image.shrink_and_check(args.output, strict_final=True)
            manifest = {
                "experimental_init_eink_bridge": True,
                "source": {"path": str(args.source.resolve()), "sha256": source_sha},
                "vendor": {"path": str(args.vendor_image.resolve()), "sha256": sha256(args.vendor_image)},
                "daemon_sha256": sha256(daemon),
                "image": {"path": str(args.output.resolve()), "sha256": sha256(args.output)},
            }
            with manifest_path.open("x") as stream:
                json.dump(manifest, stream, indent=2)
                stream.write("\n")
        except (OSError, ValueError, subprocess.CalledProcessError):
            if installed:
                args.output.unlink(missing_ok=True)
            raise
    print(f"Verified experimental image: {args.output}")
    print(f"Manifest: {manifest_path}")
    print("No device was accessed or flashed.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            print(((error.stdout or b"") + (error.stderr or b"")).decode(errors="replace"), file=sys.stderr)
        raise SystemExit(str(error))
