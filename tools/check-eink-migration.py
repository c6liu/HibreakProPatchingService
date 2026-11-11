#!/usr/bin/env python3
"""Host-only validation of e-ink control properties and socket policy; never builds an image."""

import argparse
from collections import Counter
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.hibreak import image
from tools.hibreak.policy import neverallow_failures, prepare_ir_policy
from tools.hibreak.properties import parse_contexts, resolve_context, effective_permissions


CONTROL_TYPE = "hibreak_eink_control_prop"
CONTROL_LABEL = f"u:object_r:{CONTROL_TYPE}:s0"
DESTINATIONS = {
    "sys.hibreak.request.refresh_mode": "vendor.xrz.global_refresh_mode",
    "sys.hibreak.request.aod_invert": "persist.sys.hibreak.aod_invert",
    "sys.hibreak.request.linevibrator_type": "sys.linevibrator_type",
    "sys.hibreak.request.linevibrator_touch": "sys.linevibrator_touch",
    "sys.hibreak.request.wakeup_on_volume": "sys.wakeup_on_volume",
}
VALUE_TYPES = {
    "sys.hibreak.request.refresh_mode": ("enum", "180", "178", "2147483825", "179", "183"),
    "sys.hibreak.request.aod_invert": ("enum", "true", "false"),
    "sys.hibreak.request.linevibrator_type": ("int",),
    "sys.hibreak.request.linevibrator_touch": ("int",),
    "sys.hibreak.request.wakeup_on_volume": ("int",),
}


def control_contexts(entries, additions):
    requests = parse_contexts("candidate control properties", additions)
    if len(requests) != len(DESTINATIONS) or {entry.name for entry in requests} != set(DESTINATIONS):
        raise ValueError("Expected exactly the five daemon request properties")
    for request in requests:
        if request.label != CONTROL_LABEL or request.match != "exact":
            raise ValueError(f"Invalid candidate property label/match: {request.name}")
        if request.value_type != VALUE_TYPES[request.name]:
            raise ValueError(f"Invalid candidate property value type: {request.name}")
        if any(entry.name == request.name and entry.match == "exact" for entry in entries):
            raise ValueError(f"Request property already has an exact context: {request.name}")
        if resolve_context(request.name, [*entries, *requests]) != request:
            raise ValueError(f"Request context does not resolve as expected: {request.name}")
    for destination in DESTINATIONS.values():
        if resolve_context(destination, entries) != resolve_context(destination, [*entries, *requests]):
            raise ValueError(f"Bridge changed destination label: {destination}")
    return requests


def validate(source, vendor, work, compiler):
    try:
        from setools import SELinuxPolicy, TERuleQuery
        from setools.exception import RuleNotConditional
    except ImportError as error:
        raise ValueError(f"SETools required for migration validation: {error}") from error

    platform, _, inputs = prepare_ir_policy(
        source, vendor, work, compiler, allow_existing_ir=True,
    )
    baseline_policy = SELinuxPolicy(str(work / "validated.policy"))
    command = [compiler, "-m", "-M", "true", "-G", "-c", "30", *map(str, inputs),
               "-o", str(work / "candidate.policy"), "-f", str(work / "candidate.contexts")]
    baseline = neverallow_failures(subprocess.run(command, capture_output=True))
    entries = []
    plat_contexts = ""
    for index, (img, path, required) in enumerate((
        (source, f"{image.POLICY}/plat_property_contexts", True),
        (source, "system/system_ext/etc/selinux/system_ext_property_contexts", False),
        (source, "system/product/etc/selinux/product_property_contexts", False),
        (vendor, "/etc/selinux/vendor_property_contexts", True),
        (vendor, "/odm/etc/selinux/odm_property_contexts", False),
    )):
        if image.image_exists(img, path):
            text = image.extract(img, path, work / f"property-contexts-{index}").read_text()
            entries.extend(parse_contexts(path, text))
            if index == 0:
                plat_contexts = text
        elif required:
            raise ValueError(f"Missing property contexts: {img}:{path}")
    additions = (ROOT / "tools/display/hibreak-eink-control-property-contexts").read_text()
    requests = control_contexts(entries, additions)
    destination_types = {
        resolve_context(name, entries).label.split(":")[2]
        for name in DESTINATIONS.values()
    }
    baseline_permissions = {
        target: effective_permissions(baseline_policy, target, TERuleQuery, RuleNotConditional)
        for target in destination_types
    }
    platform.write_text(platform.read_text() + "\n" +
                        (ROOT / "tools/display/hibreak-eink-candidate.cil").read_text())
    modified = neverallow_failures(subprocess.run(command, capture_output=True))
    added = modified - baseline
    if added:
        raise ValueError("Native candidate changes neverallow diagnostics:\n" + "\n".join(sorted(added)))
    image.run(*command, "-N")
    candidate = SELinuxPolicy(str(work / "candidate.policy"))
    domain = candidate.lookup_type("hibreak_eink")
    if domain.ispermissive:
        raise ValueError("Candidate domain must be enforcing")
    if "mlstrustedsubject" not in {str(attribute) for attribute in domain.attributes()}:
        raise ValueError("Categorized priv_app clients require the daemon's MLS exception")
    for target, cls, permissions in (
        ("system_file", "file", ("execute", "execute_no_trans")),
        ("toolbox_exec", "file", ("execute", "execute_no_trans")),
        ("binder_device", "chr_file", ("open", "read", "write", "ioctl")),
        ("servicemanager", "binder", ("call", "transfer")),
        ("system_server", "binder", ("call", "transfer")),
        ("system_server", "fd", ("use",)),
        ("activity_service", "service_manager", ("find",)),
        ("input_service", "service_manager", ("find",)),
        ("settings_service", "service_manager", ("find",)),
    ):
        for permission in permissions:
            rules = TERuleQuery(candidate, ruletype=["allow"], source="hibreak_eink",
                                target=target, tclass=[cls], perms=[permission]).results()
            if not any(rules):
                raise ValueError(f"Native candidate lacks {target}:{cls} {permission}")
    for target, permissions in baseline_permissions.items():
        actual = effective_permissions(candidate, target, TERuleQuery, RuleNotConditional)
        existing = {permission for permission in actual if permission[0] != "hibreak_eink"}
        inherited = actual - existing
        expected_inherited = {
            ("hibreak_eink", "file", permission)
            for permission in ("read", "open", "getattr", "map")
        } if target == "system_prop" else set()
        if existing != permissions or inherited != expected_inherited:
            raise ValueError(
                f"Destination property permissions changed unexpectedly for {target}: "
                f"lost={sorted(permissions - existing)}, gained={sorted(existing - permissions)}, "
                f"native={sorted(inherited)}"
            )
        if ("init", "property_service", "set") not in permissions:
            raise ValueError(f"Init cannot bridge to destination property type {target}")
    for target, cls, permission in (
        ("system_prop", "property_service", "set"),
        ("vendor_default_prop", "property_service", "set"),
        ("hibreak_eink", "unix_stream_socket", "connectto"),
    ):
        source_type = "priv_app" if cls == "unix_stream_socket" else "hibreak_eink"
        grants = list(TERuleQuery(candidate, ruletype=["allow"], source=source_type,
                                 target=target, tclass=[cls], perms=[permission]).results())
        if bool(grants) != (cls == "unix_stream_socket"):
            raise ValueError(f"Unexpected {source_type}->{target} {permission} grants")
    control_permissions = effective_permissions(candidate, CONTROL_TYPE, TERuleQuery, RuleNotConditional)
    if ("hibreak_eink", "property_service", "set") not in control_permissions:
        raise ValueError("Daemon cannot set request properties")
    probe = work / "control-context-probe.cil"
    probe.write_text(
        f'(filecon "/__hibreak_control_context_probe" file '
        f'(u object_r {CONTROL_TYPE} ((s0) (s0))))\n'
    )
    image.run(*command, str(probe), "-N")
    if CONTROL_LABEL not in (work / "candidate.contexts").read_text():
        raise ValueError("Compiler did not validate the control-property context")
    (work / "candidate-property-contexts").write_text(plat_contexts + "\n" + additions)
    print(f"Host control/socket scaffold passed: {len(requests)} scoped request properties; "
          f"{len(modified)} baseline conflicts, zero added "
          f"({dict(Counter(block.split()[0] for block in modified))}).")
    print("Destination labels and existing domains' effective permissions preserved; candidate domain enforcing.")
    print("The native core domain inherits read-only system_prop access; no default-property set grant.")
    print("Framework helper execution and binder grants are present; runtime behavior remains unverified.")
    print("No image created. Hardware access, helper execution and device behavior remain unverified.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--vendor-image", required=True, type=Path)
    parser.add_argument("--secilc", default="secilc")
    args = parser.parse_args()
    for tool in ("debugfs", args.secilc):
        if not tool or not shutil.which(tool):
            parser.error(f"Missing dependency: {tool}")
    for path in (args.source, args.vendor_image):
        if not path.is_file() or path.stat().st_size == 0:
            parser.error(f"Missing input: {path}")
    for path in (args.source, args.vendor_image, Path(tempfile.gettempdir())):
        if any(char in str(path) for char in ('"', "\\", "\n", "\r")):
            parser.error(f"Unsupported path characters: {path}")
    with tempfile.TemporaryDirectory(prefix="hibreak-native-migration-") as directory:
        validate(args.source, args.vendor_image, Path(directory), args.secilc)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            print(((error.stdout or b"") + (error.stderr or b"")).decode(errors="replace"),
                  file=sys.stderr)
        raise SystemExit(str(error))
