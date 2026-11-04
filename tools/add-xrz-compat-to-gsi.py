#!/usr/bin/env python3
"""Experimentally restore four Bigme graphics properties in an ext4 GSI."""

import argparse
from collections import defaultdict
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.hibreak import image
from tools.hibreak.policy import neverallow_failures, prepare_ir_policy

PROPERTIES = (
    "vendor.xrz.fps_limit",
    "vendor.xrz.gray_256_dither",
    "vendor.xrz.hwc_idle",
    "ro.vendor.xrz.screen_type",
)
DEFAULT_LABEL = "u:object_r:vendor_default_prop:s0"
XRZ_LABEL = "u:object_r:vendor_xrz_prop:s0"
PLAT_CONTEXTS = "system/etc/selinux/plat_property_contexts"
MAPPING = "system/etc/selinux/mapping/31.0.cil"
MARKER_PREFIX = "hibreak-xrz-graphics-compat-"
MARKER = MARKER_PREFIX + "v2"
COMPOSER_SET = ("hal_graphics_composer_default", "property_service", "set")
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


@dataclass(frozen=True)
class PropertyContext:
    name: str
    label: str
    match: str
    value_type: Tuple[str, ...]
    source: str


def parse_contexts(source, text):
    entries = []
    for number, line in enumerate(text.splitlines(), 1):
        fields = line.split("#", 1)[0].split()
        if not fields:
            continue
        if len(fields) < 2:
            raise ValueError(f"Invalid property context in {source}:{number}")
        match = fields[2] if len(fields) >= 3 else "prefix"
        if match not in ("exact", "prefix"):
            raise ValueError(f"Invalid property match mode in {source}:{number}: {match}")
        entries.append(PropertyContext(
            fields[0], fields[1], match, tuple(fields[3:]) or ("string",), source,
        ))
    return entries


def resolve_context(name, entries):
    matches = [
        entry for entry in entries
        if (entry.match == "exact" and name == entry.name)
        or (entry.match == "prefix" and name.startswith(entry.name))
    ]
    if not matches:
        raise ValueError(f"No property context matches {name}")
    best_rank = max((len(entry.name), entry.match == "exact") for entry in matches)
    best = [entry for entry in matches if (len(entry.name), entry.match == "exact") == best_rank]
    if len(best) != 1:
        raise ValueError(f"Ambiguous property contexts for {name}: {[entry.source for entry in best]}")
    return best[0]


def add_property_contexts(plat_text, other_contexts):
    entries = parse_contexts(PLAT_CONTEXTS, plat_text)
    for source, text in other_contexts:
        entries.extend(parse_contexts(source, text))
    for name in PROPERTIES:
        if any(entry.name == name and entry.match == "exact" for entry in entries):
            raise ValueError(f"Property already has an exact context: {name}")
        current = resolve_context(name, entries)
        if current.label != DEFAULT_LABEL or current.value_type != ("string",):
            raise ValueError(
                f"Expected generic string context for {name}, got "
                f"{current.label} {current.value_type} from {current.source}"
            )
    additions = "\n".join(f"{name} {XRZ_LABEL} exact string" for name in PROPERTIES)
    updated = plat_text.rstrip("\n") + f"\n\n# {MARKER}\n{additions}\n"
    updated_entries = parse_contexts(PLAT_CONTEXTS, updated)
    for source, text in other_contexts:
        updated_entries.extend(parse_contexts(source, text))
    for name in PROPERTIES:
        result = resolve_context(name, updated_entries)
        if result.label != XRZ_LABEL or result.value_type != ("string",):
            raise ValueError(f"New property context does not select the expected type: {name}")
    return updated


def effective_permissions(policy, target, query, not_conditional):
    permissions = set()
    for rule in query(
        policy, ruletype=["allow"], target=target,
    ).results():
        try:
            rule.conditional
        except not_conditional:
            pass
        else:
            raise ValueError(f"Conditional property permission cannot be safely preserved: {rule}")
        for source in rule.source.expand():
            permissions.update((str(source), str(rule.tclass), str(permission))
                               for permission in rule.perms)
    return permissions


def preservation_rules(baseline, mapped):
    if COMPOSER_SET in baseline:
        raise ValueError("The composer already has the generic property-set permission")
    if COMPOSER_SET not in mapped:
        raise ValueError("Stock vendor policy does not grant the expected composer property-set permission")
    unexpected = mapped - baseline - {COMPOSER_SET}
    if unexpected:
        raise ValueError(f"Mapping would add unexpected permissions: {sorted(unexpected)}")
    missing = defaultdict(set)
    for source, cls, permission in baseline - mapped:
        if not all(IDENTIFIER.fullmatch(value) for value in (source, cls, permission)):
            raise ValueError(f"Unsupported SELinux identifier: {(source, cls, permission)}")
        missing[(source, cls)].add(permission)
    return [
        f"(allow {source} vendor_xrz_prop ({cls} ({' '.join(sorted(permissions))})))"
        for (source, cls), permissions in sorted(missing.items())
    ]


def policy_command(compiler, inputs, work, name):
    return [
        compiler, "-m", "-M", "true", "-G", "-c", "30",
        *map(str, inputs), "-o", str(work / f"{name}.policy"),
        "-f", str(work / f"{name}.contexts"),
    ]


def prepare_compatibility(source, vendor, work, compiler):
    try:
        from setools import SELinuxPolicy, TERuleQuery
        from setools.exception import RuleNotConditional
    except ImportError as error:
        raise ValueError(
            f"SETools Python bindings are required for permission comparisons: {error}"
        ) from error

    platform, _, inputs = prepare_ir_policy(
        source, vendor, work, compiler, allow_existing_ir=True,
    )
    if (work / "version").read_text().strip() != "31.0":
        raise ValueError("This experimental overlay requires stock vendor policy version 31.0")
    mapping = work / "plat-mapping.cil"
    if MARKER_PREFIX in platform.read_text() or MARKER_PREFIX in mapping.read_text():
        raise ValueError("XRZ graphics compatibility overlay is already present; rebuild from the pre-XRZ image")

    plat_contexts = image.extract(source, PLAT_CONTEXTS, work / "plat-property-contexts")
    other_contexts = []
    for label, img, path, required in (
        ("system_ext", source, "system/system_ext/etc/selinux/system_ext_property_contexts", False),
        ("product", source, "system/product/etc/selinux/product_property_contexts", False),
        ("vendor", vendor, "/etc/selinux/vendor_property_contexts", True),
        ("odm", vendor, "/odm/etc/selinux/odm_property_contexts", False),
    ):
        if image.image_exists(img, path):
            text = image.extract(img, path, work / f"{label}-property-contexts").read_text()
            other_contexts.append((label, text))
        elif required:
            raise ValueError(f"Missing {label} property contexts: {img}:{path}")
    plat_contexts.write_text(add_property_contexts(plat_contexts.read_text(), other_contexts))

    baseline_policy = SELinuxPolicy(str(work / "validated.policy"))
    xrz_type = baseline_policy.lookup_type("vendor_xrz_prop")
    if "vendor_xrz_prop_31_0" in {str(attribute) for attribute in xrz_type.attributes()}:
        raise ValueError("The vendor_xrz_prop_31_0 mapping is already present")
    baseline = effective_permissions(
        baseline_policy, "vendor_default_prop", TERuleQuery, RuleNotConditional,
    )
    normal = policy_command(compiler, inputs, work, "normal")
    baseline_conflicts = neverallow_failures(subprocess.run(normal, capture_output=True))

    mapping.write_text(
        mapping.read_text().rstrip("\n")
        + f"\n\n; {MARKER}\n(typeattributeset vendor_xrz_prop_31_0 (vendor_xrz_prop))\n"
    )
    mapped_command = policy_command(compiler, inputs, work, "mapped")
    image.run(*mapped_command, "-N")
    mapped_policy = SELinuxPolicy(str(work / "mapped.policy"))
    mapped = effective_permissions(mapped_policy, "vendor_xrz_prop", TERuleQuery, RuleNotConditional)
    rules = preservation_rules(baseline, mapped)
    platform.write_text(
        platform.read_text().rstrip("\n") + f"\n\n; {MARKER}\n" + "\n".join(rules) + "\n"
    )

    final_conflicts = neverallow_failures(subprocess.run(normal, capture_output=True))
    added_conflicts = final_conflicts - baseline_conflicts
    if added_conflicts:
        raise ValueError("XRZ overlay adds neverallow violations:\n" + "\n".join(sorted(added_conflicts)))
    context_probe = work / "xrz-context-check.cil"
    context_probe.write_text(
        '(filecon "/__hibreak_xrz_context_check" file '
        '(u object_r vendor_xrz_prop ((s0) (s0))))\n'
    )
    final_command = policy_command(compiler, [*inputs, context_probe], work, "final")
    image.run(*final_command, "-N")
    if XRZ_LABEL not in (work / "final.contexts").read_text():
        raise ValueError("The compiler did not validate the XRZ property context")
    final_policy = SELinuxPolicy(str(work / "final.policy"))
    final_type = final_policy.lookup_type("vendor_xrz_prop")
    attributes = {str(attribute) for attribute in final_type.attributes()}
    if not {"property_type", "vendor_xrz_prop_31_0"} <= attributes:
        raise ValueError("The mapped XRZ type is not a versioned SELinux property type")
    final = effective_permissions(final_policy, "vendor_xrz_prop", TERuleQuery, RuleNotConditional)
    if baseline - final or final - baseline != {COMPOSER_SET}:
        raise ValueError(
            f"Property permissions differ from the expected result: "
            f"lost={sorted(baseline - final)}, gained={sorted(final - baseline)}"
        )

    digest = hashlib.sha256()
    for path in inputs:
        digest.update(path.read_bytes())
    digest_file = work / "policy-digest"
    digest_file.write_text(digest.hexdigest() + "\n")
    vendor_digest = "/etc/selinux/precompiled_sepolicy.plat_sepolicy_and_mapping.sha256"
    if image.image_exists(vendor, vendor_digest):
        previous = image.extract(vendor, vendor_digest, work / "vendor-policy-digest").read_text().strip()
        if not re.fullmatch(r"[0-9a-fA-F]{64}", previous):
            raise ValueError("Invalid vendor precompiled policy digest")
        if previous.lower() == digest.hexdigest():
            raise ValueError("Updated policy digest matches the vendor's precompiled policy")

    print(f"Preserved {len(baseline)} existing effective allow permissions "
          f"using {len(rules)} explicit rules.")
    print("For these properties, the only added effective allow is the composer's property_service set.")
    if baseline_conflicts:
        print(f"WARNING: {len(baseline_conflicts)} existing GSI/vendor neverallow conflicts remain.")
    return platform, mapping, plat_contexts, digest_file


def build_image(source, output, files, work):
    destinations = (
        f"{image.POLICY}/plat_sepolicy.cil",
        MAPPING,
        PLAT_CONTEXTS,
        f"{image.POLICY}/plat_sepolicy_and_mapping.sha256",
    )
    if len(files) != len(destinations):
        raise ValueError("Expected exactly four XRZ policy inputs")
    complete = False
    try:
        image.copy_and_grow(source, output, 32 * 1024 * 1024)
        for file, dest in zip(files, destinations):
            image.install(output, file, dest, "0100644", "u:object_r:system_file:s0", work)
        image.shrink_and_check(output, strict_final=True)
        complete = True
    finally:
        if not complete:
            output.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Raw ext4 GSI, with or without the IR overlay")
    parser.add_argument("output", type=Path, help="New experimental image; never overwritten")
    parser.add_argument("--vendor-image", required=True, type=Path,
                        help="Read-only stock vendor ext4 image matching the target phone")
    parser.add_argument("--secilc", default="secilc", help="Host CIL compiler")
    parser.add_argument("--check-only", action="store_true", help="Validate without producing an image")
    args = parser.parse_args()
    for tool in ("debugfs", "e2fsck", "resize2fs", "dumpe2fs", "cp", args.secilc):
        if not shutil.which(tool):
            parser.error(f"Missing dependency: {tool}")
    for path in (args.source, args.vendor_image):
        if not path.is_file() or path.stat().st_size == 0:
            parser.error(f"Missing input: {path}")
    for path in (args.source, args.vendor_image, args.output, ROOT, Path(tempfile.gettempdir())):
        if any(char in str(path) for char in ('"', "\\", "\n", "\r")):
            parser.error(f"Unsupported path characters: {path}")
    if os.path.lexists(args.output):
        parser.error(f"Refusing to overwrite: {args.output}")
    with tempfile.TemporaryDirectory(prefix="hibreak-xrz-") as directory:
        work = Path(directory)
        files = prepare_compatibility(args.source, args.vendor_image, work, args.secilc)
        if args.check_only:
            print("Preflight passed; no image was written.")
            return
        build_image(args.source, args.output, files, work)
    print(f"Verified experimental system image: {args.output}")
    print("No vendor partition was modified and no device was accessed.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            print(((error.stdout or b"") + (error.stderr or b"")).decode(errors="replace"),
                  file=sys.stderr)
        raise SystemExit(str(error))
