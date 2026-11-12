#!/usr/bin/env python3
"""Build an opt-in enforcing display/AOD helper image from the tested daemon image."""

import argparse
from collections import Counter
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
from tools.hibreak.policy import neverallow_failures, prepare_ir_policy
from tools.hibreak.properties import effective_permissions, parse_contexts, resolve_context
from tools.hibreak.tested_stages import validate_rebuild

SPEC = importlib.util.spec_from_file_location("eink_image", ROOT / "tools/add-eink-migration-to-gsi.py")
eink_image = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(eink_image)

SOURCE_SHA256 = "6077c0eee9b37038ac35d5f3b08106aa3280b29073787c41404a72666fbd8bff"
DISPLAY = ROOT / "tools/display"
INIT_PATH = "system/etc/init/hibreak-display.rc"
AOD_PATH = "system/bin/hibreak-aod.sh"
PROPERTY_CONTEXTS = f"{image.POLICY}/plat_property_contexts"
STATE_NAMES = ("persist.sys.hibreak.display.aod_inverted", "persist.sys.hibreak.display.aod_setup")
STATE_LABEL = "u:object_r:hibreak_display_state_prop:s0"
LEGACY_NAMES = ("persist.sys.hibreak.aod_inverted", "persist.sys.hibreak.aod_setup")


def migrate_init(text):
    old = "    seclabel u:r:phhsu_daemon:s0"
    if text.count(old) != 5:
        raise ValueError("Expected exactly five original display helper labels")
    return text.replace(old, "    seclabel u:r:hibreak_display:s0")


def migrate_aod(text):
    marker = "MARK=persist.sys.hibreak.aod_inverted"
    setup = "persist.sys.hibreak.aod_setup"
    if text.count(marker) != 1 or text.count(setup) != 2:
        raise ValueError("Unexpected original AOD state handling")
    text = text.replace(marker, "MARK=" + STATE_NAMES[0]).replace(setup, STATE_NAMES[1])
    bootstrap = """
if [ -z "$(getprop persist.sys.hibreak.display.aod_inverted)" ] &&
        [ "$(getprop persist.sys.hibreak.aod_inverted)" = "1" ]; then
    setprop persist.sys.hibreak.display.aod_inverted 1
fi
if [ -z "$(getprop persist.sys.hibreak.display.aod_setup)" ] &&
        [ "$(getprop persist.sys.hibreak.aod_setup)" = "1" ]; then
    setprop persist.sys.hibreak.display.aod_setup 1
fi
"""
    return text.replace("MARK=" + STATE_NAMES[0] + "\n", "MARK=" + STATE_NAMES[0] + "\n" + bootstrap)


def add_contexts(platform, other):
    entries = parse_contexts(PROPERTY_CONTEXTS, platform)
    for source, text in other:
        entries.extend(parse_contexts(source, text))
    additions = (DISPLAY / "hibreak-display-state-property-contexts").read_text()
    requests = parse_contexts("display state", additions)
    if len(requests) != 2 or {entry.name for entry in requests} != set(STATE_NAMES):
        raise ValueError("Expected exactly two display state properties")
    for entry in requests:
        if (entry.label, entry.match, entry.value_type) != (STATE_LABEL, "exact", ("enum", "0", "1")):
            raise ValueError(f"Invalid display state context: {entry.name}")
        if any(old.name == entry.name and old.match == "exact" for old in entries):
            raise ValueError(f"Display state property already exists: {entry.name}")
        baseline = resolve_context(entry.name, entries)
        if baseline.label != "u:object_r:system_prop:s0" or baseline.value_type != ("string",):
            raise ValueError(f"Unexpected prior display state context: {entry.name}")
        if resolve_context(entry.name, [*entries, *requests]) != entry:
            raise ValueError(f"Display state property is ambiguous: {entry.name}")
    for name in (*LEGACY_NAMES, "persist.sys.hibreak.aod_invert",
                 "persist.sys.hibreak.boot_sleep_cycle"):
        if resolve_context(name, entries) != resolve_context(name, [*entries, *requests]):
            raise ValueError(f"Existing display property context changed: {name}")
    return platform.rstrip("\n") + "\n\n# experimental display helper state\n" + additions


def prepare(source, vendor, work, compiler):
    from setools import SELinuxPolicy, TERuleQuery
    from setools.exception import RuleNotConditional

    platform, _, inputs = prepare_ir_policy(source, vendor, work, compiler, allow_existing_ir=True)
    baseline_policy = SELinuxPolicy(str(work / "validated.policy"))
    if "hibreak_display_state_prop" in platform.read_text():
        raise ValueError("Display helper migration already present")
    contexts = image.extract(source, PROPERTY_CONTEXTS, work / "display-properties")
    other = []
    for name, img, path, required in (
        ("system_ext", source, "system/system_ext/etc/selinux/system_ext_property_contexts", False),
        ("product", source, "system/product/etc/selinux/product_property_contexts", False),
        ("vendor", vendor, "/etc/selinux/vendor_property_contexts", True),
        ("odm", vendor, "/odm/etc/selinux/odm_property_contexts", False),
    ):
        if image.image_exists(img, path):
            other.append((name, image.extract(img, path, work / (name + "-properties")).read_text()))
        elif required:
            raise ValueError(f"Missing {name} property contexts")
    contexts.write_text(add_contexts(contexts.read_text(), other))
    init = image.extract(source, INIT_PATH, work / "display.rc")
    init.write_text(migrate_init(init.read_text()))
    aod = image.extract(source, AOD_PATH, work / "hibreak-aod.sh")
    aod.write_text(migrate_aod(aod.read_text()))
    image.run("sh", "-n", str(aod))
    command = [compiler, "-m", "-M", "true", "-G", "-c", "30", *map(str, inputs),
               "-o", str(work / "display.policy"), "-f", str(work / "display.contexts")]
    baseline = neverallow_failures(subprocess.run(command, capture_output=True))
    original_system = effective_permissions(baseline_policy, "system_prop", TERuleQuery, RuleNotConditional)
    platform.write_text(platform.read_text().rstrip("\n") + "\n\n" +
                        (DISPLAY / "hibreak-display-migration.cil").read_text())
    changed = neverallow_failures(subprocess.run(command, capture_output=True))
    if changed - baseline:
        raise ValueError("Display helper policy changes neverallow diagnostics:\n" +
                         "\n".join(sorted(changed - baseline)))
    probe = work / "display-context-probe.cil"
    probe.write_text('(filecon "/__hibreak_display_context_probe" file '
                     '(u object_r hibreak_display_state_prop ((s0) (s0))))\n')
    image.run(*command, str(probe), "-N")
    if STATE_LABEL not in (work / "display.contexts").read_text():
        raise ValueError("Compiler did not validate display property context")
    candidate = SELinuxPolicy(str(work / "display.policy"))
    if candidate.lookup_type("hibreak_display").ispermissive:
        raise ValueError("Display helper domain must be enforcing")
    new_system = effective_permissions(candidate, "system_prop", TERuleQuery, RuleNotConditional)
    existing = {item for item in new_system if item[0] != "hibreak_display"}
    inherited = new_system - existing
    expected = {("hibreak_display", "file", permission) for permission in ("read", "open", "getattr", "map")}
    if existing != original_system or inherited != expected:
        raise ValueError("Unexpected generic system property access change")
    state_permissions = effective_permissions(candidate, "hibreak_display_state_prop", TERuleQuery, RuleNotConditional)
    writers = {src for src, cls, perm in state_permissions if cls == "property_service" and perm == "set"}
    if writers != {"init", "hibreak_display"}:
        raise ValueError(f"Unexpected display state property writers: {sorted(writers)}")
    for src, target, cls, permission in (
        ("init", "hibreak_display", "process", "transition"),
        ("hibreak_display", "shell_exec", "file", "entrypoint"),
        ("hibreak_display", "system_file", "file", "execute_no_trans"),
        ("hibreak_display", "servicemanager", "binder", "call"),
        ("hibreak_display", "surfaceflinger", "binder", "call"),
        ("hibreak_display", "system_server", "binder", "call"),
        ("system_server", "hibreak_display", "binder", "call"),
        ("hibreak_display", "surfaceflinger_service", "service_manager", "find"),
        ("hibreak_display", "settings_service", "service_manager", "find"),
        ("hibreak_display", "input_service", "service_manager", "find"),
        ("hibreak_display", "overlay_service", "service_manager", "find"),
    ):
        if not any(TERuleQuery(candidate, ruletype=["allow"], source=src, target=target,
                               tclass=[cls], perms=[permission]).results()):
            raise ValueError(f"Missing helper grant {src}->{target}:{cls} {permission}")
    print(f"Policy: {len(baseline)} existing diagnostic blocks; none added "
          f"({dict(Counter(block.split()[0] for block in baseline))}).", flush=True)
    digest = eink_image.policy_digest(inputs, vendor, work)
    return platform, contexts, init, aod, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--vendor-image", type=Path, required=True)
    parser.add_argument("--secilc", default="secilc")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--rebuild-gsi", type=Path,
                        help="Verify critical stage inputs against the tested GSI rebuild")
    args = parser.parse_args()
    for tool in ("debugfs", "e2fsck", "resize2fs", "dumpe2fs", "cp", "sh", args.secilc):
        if not shutil.which(tool):
            parser.error(f"Missing dependency: {tool}")
    for path in (args.source, args.vendor_image):
        if not path.is_file() or path.stat().st_size == 0:
            parser.error(f"Missing input: {path}")
    for path in (args.source, args.vendor_image, args.output, ROOT, Path(tempfile.gettempdir())):
        if any(char in str(path) for char in ('"', "\\", "\n", "\r")):
            parser.error(f"Unsupported path characters: {path}")
    manifest_path = args.output.with_name(args.output.name + ".manifest.json")
    if os.path.lexists(args.output) or os.path.lexists(manifest_path):
        parser.error("Refusing to overwrite image or manifest")
    source_sha = eink_image.sha256(args.source)
    if args.rebuild_gsi:
        validate_rebuild(args.source, args.vendor_image, args.rebuild_gsi, "daemon")
    elif source_sha != SOURCE_SHA256:
        parser.error("Requires the exact user-tested enforcing daemon image")
    with tempfile.TemporaryDirectory(prefix="hibreak-display-migration-") as directory:
        work = Path(directory)
        platform, contexts, init, aod, digest = prepare(args.source, args.vendor_image, work, args.secilc)
        if args.check_only:
            print("Preflight passed; no image written.")
            return
        installed = False
        manifest_created = False
        try:
            image.copy_and_grow(args.source, args.output, 32 * 1024 * 1024)
            installed = True
            for file, dest, mode in (
                (platform, f"{image.POLICY}/plat_sepolicy.cil", "0100644"),
                (contexts, PROPERTY_CONTEXTS, "0100644"),
                (digest, f"{image.POLICY}/plat_sepolicy_and_mapping.sha256", "0100644"),
                (init, INIT_PATH, "0100644"),
                (aod, AOD_PATH, "0100755"),
            ):
                image.install(args.output, file, dest, mode, "u:object_r:system_file:s0", work)
            image.shrink_and_check(args.output, strict_final=True)
            manifest = {
                "experimental_enforcing_display_helpers": True,
                "source": {"path": str(args.source.resolve()), "sha256": source_sha},
                "vendor": {"path": str(args.vendor_image.resolve()), "sha256": eink_image.sha256(args.vendor_image)},
                "image": {"path": str(args.output.resolve()), "sha256": eink_image.sha256(args.output)},
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
    print(f"Experimental helper migration image: {args.output}")
    print(f"Manifest: {manifest_path}")
    print("No device was accessed or flashed; device validation is required.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            print(((error.stdout or b"") + (error.stderr or b"")).decode(errors="replace"), file=sys.stderr)
        raise SystemExit(str(error))
