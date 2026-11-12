"""Prepare and validate the init e-ink bridge policy."""

import hashlib
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
from tools.hibreak import image
from tools.hibreak.policy import compile_pair, neverallow_failures, prepare_ir_policy
from tools.hibreak.properties import effective_permissions, parse_contexts, resolve_context
LABEL = "u:object_r:hibreak_eink_bridge_prop:s0"
REQUESTS = ("sys.hibreak.eink_bridge.auto_refresh", "sys.hibreak.eink_bridge.anti_flicker")
NODES = ("/eink_debug/clean_a2", "/eink_debug/anti_flicker")
DISPLAY = ROOT / "tools/display"
PLAT_CONTEXTS = f"{image.POLICY}/plat_property_contexts"


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


def validate_bridge_policy(policy, old_file, *, enforcing=False):
    from setools import TERuleQuery
    from setools.exception import RuleNotConditional

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
    expected_writers = {"init", "phhsu_daemon"}
    if enforcing:
        expected_writers.add("hibreak_eink")
    if writers != expected_writers:
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


def prepare_bridge(source, vendor, work, compiler, *, parallel_compile=False):
    from setools import SELinuxPolicy, TERuleQuery
    from setools.exception import RuleNotConditional

    diagnostics = []
    platform, _, inputs = prepare_ir_policy(source, vendor, work, compiler, allow_existing_ir=True,
                                            diagnostics_out=diagnostics, parallel_compile=parallel_compile)
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
    baseline = diagnostics[0]
    platform.write_text(original.rstrip("\n") + "\n\n" +
                        (DISPLAY / "hibreak-init-eink-bridge.cil").read_text())
    changed = (compile_pair(command) if parallel_compile
               else neverallow_failures(subprocess.run(command, capture_output=True)))
    if changed - baseline:
        raise ValueError("Bridge changes neverallow diagnostics:\n" + "\n".join(sorted(changed - baseline)))
    if not parallel_compile:
        image.run(*command, "-N")
    policy = SELinuxPolicy(str(work / "bridge.policy"))
    validate_bridge_policy(policy, old_file)
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
