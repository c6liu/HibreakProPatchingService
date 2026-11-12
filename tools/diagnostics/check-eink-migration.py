#!/usr/bin/env python3
"""Host-only validation of e-ink control properties and socket policy; never builds an image."""

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.hibreak import image
from tools.hibreak.policy import compile_pair, neverallow_failures, prepare_ir_policy
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
BRIDGE_TYPE = "hibreak_eink_bridge_prop"
BRIDGE_REQUESTS = (
    "sys.hibreak.eink_bridge.auto_refresh",
    "sys.hibreak.eink_bridge.anti_flicker",
)
FRONTLIGHT_TYPE = "hibreak_eink_frontlight"
FRONTLIGHT_PATHS = (
    "/devices/platform/11d01000.i2c7/i2c-7/7-0036/lm3630a_cold_light",
    "/devices/platform/11d01000.i2c7/i2c-7/7-0036/lm3630a_warm_light",
)


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


def validate_bridge_contexts(entries):
    for name in BRIDGE_REQUESTS:
        entry = resolve_context(name, entries)
        if (entry.name, entry.label, entry.match, entry.value_type) != (
            name, f"u:object_r:{BRIDGE_TYPE}:s0", "exact", ("enum", "0", "1")
        ):
            raise ValueError(f"Expected tested init bridge property context: {name}")


def frontlight_preservation_rules(baseline, candidate):
    grouped = defaultdict(set)
    for source, cls, permission in baseline - candidate:
        if cls != "file":
            raise ValueError(f"Unexpected frontlight permission class: {cls}")
        grouped[source].add(permission)
    return [
        f"(allow {source} {FRONTLIGHT_TYPE} (file ({' '.join(sorted(permissions))})))"
        for source, permissions in sorted(grouped.items())
    ]


def extended_file_permissions(policy, target, query, not_conditional):
    permissions = set()
    for rule in query(policy, ruletype=["allowxperm"], target=target, tclass=["file"]).results():
        try:
            rule.conditional
        except not_conditional:
            pass
        else:
            raise ValueError(f"Conditional extended sysfs permission cannot be preserved: {rule}")
        for source in rule.source.expand():
            permissions.update((str(source), str(rule.xperm_type), permission)
                               for permission in rule.perms)
    return permissions


def validate_frontlight_xperms(actual, baseline, *, display_migrated=False, generic_display=None):
    existing = {item for item in actual if item[0] != "hibreak_eink" and
                not (display_migrated and item[0] == "hibreak_display")}
    if existing != baseline:
        raise ValueError("Existing extended sysfs file permissions changed: "
                         f"lost={baseline - existing}, added={existing - baseline}")
    if display_migrated:
        display = {item for item in actual if item[0] == "hibreak_display"}
        if display != generic_display:
            raise ValueError("Display helper extended frontlight permissions differ from generic sysfs")


def validate_candidate_policy(candidate, baseline_permissions, bridge_permissions,
                              sysfs_file, sysfs_xperms, with_init_bridge,
                              complete_candidate, *, display_migrated=False):
    from setools import TERuleQuery
    from setools.exception import RuleNotConditional

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
    if not any(TERuleQuery(candidate, ruletype=["allow"], source="system_server",
                           target="hibreak_eink", tclass=["binder"], perms=["call"]).results()):
        raise ValueError("System server cannot deliver Binder callbacks to the daemon's helpers")
    for target, permissions in baseline_permissions.items():
        actual = effective_permissions(candidate, target, TERuleQuery, RuleNotConditional)
        existing = {permission for permission in actual if permission[0] != "hibreak_eink" and
                    not (display_migrated and permission[0] == "hibreak_display")}
        inherited = actual - existing
        expected_inherited = {
            ("hibreak_eink", "file", permission)
            for permission in ("read", "open", "getattr", "map")
        } if target == "system_prop" else set()
        if display_migrated and target == "system_prop":
            expected_inherited |= {
                ("hibreak_display", "file", permission)
                for permission in ("read", "open", "getattr", "map")
            }
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
    for permission in ("read", "write"):
        if not any(TERuleQuery(candidate, ruletype=["allow"], source="priv_app",
                               target="hibreak_eink", tclass=["unix_stream_socket"],
                               perms=[permission]).results()):
            raise ValueError(f"Candidate socket lacks client {permission} permission")
    control_permissions = effective_permissions(candidate, CONTROL_TYPE, TERuleQuery, RuleNotConditional)
    if ("hibreak_eink", "property_service", "set") not in control_permissions:
        raise ValueError("Daemon cannot set request properties")
    if with_init_bridge:
        actual = effective_permissions(candidate, BRIDGE_TYPE, TERuleQuery, RuleNotConditional)
        if {item for item in actual if item[0] != "hibreak_eink"} != bridge_permissions:
            raise ValueError("Existing init bridge property permissions changed")
        writers = {src for src, cls, perm in actual if cls == "property_service" and perm == "set"}
        if writers != {"init", "phhsu_daemon", "hibreak_eink"}:
            raise ValueError(f"Unexpected init bridge property writers: {sorted(writers)}")
    if complete_candidate:
        actual = {item for item in effective_permissions(
            candidate, FRONTLIGHT_TYPE, TERuleQuery, RuleNotConditional,
        ) if item[1] == "file"}
        expected = {("hibreak_eink", "file", permission) for permission in ("open", "write")}
        if sysfs_file - actual or actual - sysfs_file != expected:
            raise ValueError(f"Unexpected frontlight permissions: lost={sysfs_file - actual}, "
                             f"added={actual - sysfs_file}")
        actual_xperms = extended_file_permissions(
            candidate, FRONTLIGHT_TYPE, TERuleQuery, RuleNotConditional,
        )
        generic_display_xperms = None
        if display_migrated:
            generic_display_xperms = {
                item for item in extended_file_permissions(candidate, "sysfs", TERuleQuery, RuleNotConditional)
                if item[0] == "hibreak_display"
            }
        validate_frontlight_xperms(actual_xperms, sysfs_xperms, display_migrated=display_migrated,
                                  generic_display=generic_display_xperms)
        for node in FRONTLIGHT_PATHS:
            if not any(rule.fs == "sysfs" and str(rule.path) == node and
                       str(rule.context.type_) == FRONTLIGHT_TYPE for rule in candidate.genfscons()):
                raise ValueError(f"Frontlight node label missing: {node}")
        for target, cls, permissions in (
            ("system_data_file", "dir", ("search",)),
            ("packages_list_file", "file", ("open", "read", "getattr")),
        ):
            for permission in permissions:
                if not any(TERuleQuery(candidate, ruletype=["allow"], source="hibreak_eink",
                                       target=target, tclass=[cls], perms=[permission]).results()):
                    raise ValueError(f"Candidate cannot access package registry: {target}:{cls} {permission}")


def validate(source, vendor, work, compiler, with_init_bridge=False, complete_candidate=False,
             *, parallel_compile=False):
    try:
        from setools import SELinuxPolicy, TERuleQuery
        from setools.exception import RuleNotConditional
    except ImportError as error:
        raise ValueError(f"SETools required for migration validation: {error}") from error

    diagnostics = []
    platform, _, inputs = prepare_ir_policy(
        source, vendor, work, compiler, allow_existing_ir=True, diagnostics_out=diagnostics,
        parallel_compile=parallel_compile,
    )
    baseline_policy = SELinuxPolicy(str(work / "validated.policy"))
    command = [compiler, "-m", "-M", "true", "-G", "-c", "30", *map(str, inputs),
               "-o", str(work / "candidate.policy"), "-f", str(work / "candidate.contexts")]
    baseline = diagnostics[0]
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
    if with_init_bridge:
        validate_bridge_contexts(entries)
        bridge_permissions = effective_permissions(
            baseline_policy, BRIDGE_TYPE, TERuleQuery, RuleNotConditional,
        )
    if complete_candidate:
        if not with_init_bridge:
            raise ValueError("Complete candidate requires the tested init bridge")
        sysfs_xperms = extended_file_permissions(
            baseline_policy, "sysfs", TERuleQuery, RuleNotConditional,
        )
        for node in FRONTLIGHT_PATHS:
            matching = [rule for rule in baseline_policy.genfscons()
                        if rule.fs == "sysfs" and
                        (str(rule.path) == node or node.startswith(str(rule.path).rstrip("/") + "/"))]
            if not matching or str(max(matching, key=lambda rule: len(str(rule.path))).context.type_) != "sysfs":
                raise ValueError(f"Expected generic sysfs baseline for {node}")
        sysfs_file = {item for item in effective_permissions(
            baseline_policy, "sysfs", TERuleQuery, RuleNotConditional,
        ) if item[1] == "file"}
    destination_types = {
        resolve_context(name, entries).label.split(":")[2]
        for name in DESTINATIONS.values()
    }
    baseline_permissions = {
        target: effective_permissions(baseline_policy, target, TERuleQuery, RuleNotConditional)
        for target in destination_types
    }
    candidate_cil = (ROOT / "tools/display/hibreak-eink-candidate.cil").read_text()
    if with_init_bridge:
        candidate_cil += "\n" + (ROOT / "tools/display/hibreak-eink-bridge-client.cil").read_text()
    if complete_candidate:
        candidate_cil += "\n" + (ROOT / "tools/display/hibreak-eink-runtime.cil").read_text()
    platform.write_text(platform.read_text() + "\n" + candidate_cil)
    if complete_candidate:
        image.run(*command, "-N")
        preliminary = SELinuxPolicy(str(work / "candidate.policy"))
        current_file = {item for item in effective_permissions(
            preliminary, FRONTLIGHT_TYPE, TERuleQuery, RuleNotConditional,
        ) if item[1] == "file"}
        rules = frontlight_preservation_rules(sysfs_file, current_file)
        platform.write_text(platform.read_text() + "\n" + "\n".join(rules) + "\n")
    modified = (compile_pair(command) if parallel_compile
                else neverallow_failures(subprocess.run(command, capture_output=True)))
    added = modified - baseline
    if added:
        raise ValueError("Native candidate changes neverallow diagnostics:\n" + "\n".join(sorted(added)))
    if not parallel_compile:
        image.run(*command, "-N")
    candidate = SELinuxPolicy(str(work / "candidate.policy"))
    validate_candidate_policy(candidate, baseline_permissions,
                              bridge_permissions if with_init_bridge else None,
                              sysfs_file if complete_candidate else None,
                              sysfs_xperms if complete_candidate else None,
                              with_init_bridge, complete_candidate)
    probe = work / "control-context-probe.cil"
    probe_text = (
        f'(filecon "/__hibreak_control_context_probe" file '
        f'(u object_r {CONTROL_TYPE} ((s0) (s0))))\n'
    )
    if complete_candidate:
        probe_text += ('(filecon "/__hibreak_exec_context_probe" file '
                       '(u object_r hibreak_eink_exec ((s0) (s0))))\n')
    probe.write_text(probe_text)
    image.run(*command, str(probe), "-N")
    if CONTROL_LABEL not in (work / "candidate.contexts").read_text():
        raise ValueError("Compiler did not validate the control-property context")
    if complete_candidate and "u:object_r:hibreak_eink_exec:s0" not in (work / "candidate.contexts").read_text():
        raise ValueError("Compiler did not validate the executable context")
    (work / "candidate-property-contexts").write_text(plat_contexts + "\n" + additions)
    print(f"Host control/socket scaffold passed: {len(requests)} scoped request properties; "
          f"{len(modified)} baseline conflicts, zero added "
          f"({dict(Counter(block.split()[0] for block in modified))}).")
    print("Destination labels and existing domains' effective permissions preserved; candidate domain enforcing.")
    print("The native core domain inherits read-only system_prop access; no default-property set grant.")
    print("Framework helper execution and binder grants are present; runtime behavior remains unverified.")
    if with_init_bridge:
        print("Tested init bridge accepts the candidate domain; existing bridge permissions preserved.")
    if complete_candidate:
        print("Frontlight file permissions preserved; package-registry access granted for peer authentication.")
    print("No image created. Hardware access, helper execution and device behavior remain unverified.")
    return platform, work / "candidate-property-contexts", inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--vendor-image", required=True, type=Path)
    parser.add_argument("--secilc", default="secilc")
    parser.add_argument("--with-init-bridge", action="store_true",
                        help="Validate the candidate against an image containing the tested init bridge")
    parser.add_argument("--complete-candidate", action="store_true",
                        help="Also validate frontlight and package-registry access")
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
        validate(args.source, args.vendor_image, Path(directory), args.secilc,
                 args.with_init_bridge or args.complete_candidate, args.complete_candidate)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            print(((error.stdout or b"") + (error.stderr or b"")).decode(errors="replace"),
                  file=sys.stderr)
        raise SystemExit(str(error))
