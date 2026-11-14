"""Prepare the tested release policy and validate its combined result."""

import hashlib
import subprocess

from tools.hibreak import display_migration, eink_bridge, eink_migration, image
from tools.hibreak.policy import compile_pair, extract_policy_inputs, neverallow_failures
from tools.hibreak.properties import effective_permissions, parse_contexts, resolve_context
from tools.hibreak.tested_stages import validate_rebuild

SYSTEM = "u:object_r:system_file:s0"
ROOT = eink_migration.ROOT


def validate_final_conflicts(baseline, conflicts):
    added = conflicts - baseline
    if added:
        raise ValueError("Combined policy adds neverallow diagnostics:\n" + "\n".join(sorted(added)))


def prepare(target, gsi, vendor, hal, daemon, compiler, work, load, *, parallel_compile):
    from setools import SELinuxPolicy, TERuleQuery
    from setools.exception import RuleNotConditional

    xrz = load("final_xrz", "add-xrz-compat-to-gsi.py")
    phh = load("final_phh", "add-phh-reduction-to-gsi.py")
    migration = eink_migration.migration
    platform, inputs = extract_policy_inputs(target, vendor, work)
    if (work / "version").read_text().strip() != "31.0":
        raise ValueError("XRZ requires stock vendor policy version 31.0")
    mapping = work / "plat-mapping.cil"
    ext = work / "ext.cil"
    if ext not in inputs:
        raise ValueError("GSI has no system-ext policy")
    if xrz.MARKER_PREFIX in mapping.read_text() or xrz.MARKER_PREFIX in platform.read_text():
        raise ValueError("XRZ compatibility overlay already present")

    stock = image.extract(vendor, "/lib64/hw/consumerir.common.so", work / "stock-ir.so")
    service = image.extract(vendor, "/etc/init/android.hardware.ir@1.0-service.rc", work / "stock-ir.rc")
    if stock.read_bytes()[:6] != b"\x7fELF\x02\x01" or "class hal" not in service.read_text():
        raise ValueError("Expected arm64 legacy consumerir.common.so and class-hal IR service")
    from tools.hibreak.elf import validate_hal_module
    validate_hal_module(hal)

    files = {}
    base_files = {
        "system/priv-app/EinkSettings/HiBreakEink.apk": ("0644", SYSTEM),
        "system/etc/permissions/privapp-permissions-hibreak-eink.xml": ("0644", SYSTEM),
        "system/bin/hibreak-disable-hwc.sh": ("0755", SYSTEM),
        "system/bin/hibreak-wake-cycle.sh": ("0755", SYSTEM),
        "system/build.prop": ("0644", SYSTEM),
    }
    for path in ("system/system_ext/etc/build.prop", "system/product/etc/build.prop"):
        if image.image_exists(target, path):
            base_files[path] = ("0644", SYSTEM)
    for destination, (mode, label) in base_files.items():
        content = image.extract(target, destination, work / "base-file")
        files[destination] = (hashlib.sha256(content.read_bytes()).hexdigest(), mode, label)
        content.unlink()

    def install(source, destination, mode="0100644", label=SYSTEM):
        image.install(target, source, destination, mode, label, work)
        files[destination] = (hashlib.sha256(source.read_bytes()).hexdigest(), mode[-4:], label)

    def compile_runtime(name):
        command = [compiler, "-m", "-M", "true", "-G", "-c", "30",
                   *map(str, inputs), "-o", str(work / f"{name}.policy"),
                   "-f", str(work / f"{name}.contexts"), "-N"]
        image.run(*command)
        return SELinuxPolicy(str(work / f"{name}.policy"))

    def permissions(policy, target_type):
        return effective_permissions(policy, target_type, TERuleQuery, RuleNotConditional)

    def digest():
        return eink_migration.policy_digest(inputs, vendor, work)

    property_contexts = image.extract(target, xrz.PLAT_CONTEXTS, work / "properties")
    file_contexts = image.extract(target, f"{image.POLICY}/plat_file_contexts", work / "file-contexts")
    others = []
    for label, img, path, required in (
        ("system_ext", target, "system/system_ext/etc/selinux/system_ext_property_contexts", False),
        ("product", target, "system/product/etc/selinux/product_property_contexts", False),
        ("vendor", vendor, "/etc/selinux/vendor_property_contexts", True),
        ("odm", vendor, "/odm/etc/selinux/odm_property_contexts", False),
    ):
        if image.image_exists(img, path):
            others.append((label, image.extract(img, path, work / f"{label}-properties").read_text()))
        elif required:
            raise ValueError(f"Missing {label} property contexts")

    platform.write_text(platform.read_text() + "\n\n" + (ROOT / "tools/ir/hibreak-ir-hal.cil").read_text())
    file_contexts.write_text(file_contexts.read_text() +
                             "\n/system/lib64/consumerir\\.hxd\\.so u:object_r:hibreak_ir_hal_file:s0\n")
    base = compile_runtime("xrz-base")
    if "vendor_xrz_prop_31_0" in {str(a) for a in base.lookup_type("vendor_xrz_prop").attributes()}:
        raise ValueError("XRZ mapping already present")
    xrz_baseline = permissions(base, "vendor_default_prop")
    mapping.write_text(mapping.read_text().rstrip("\n") +
                       f"\n\n; {xrz.MARKER}\n(typeattributeset vendor_xrz_prop_31_0 (vendor_xrz_prop))\n")
    mapped = compile_runtime("xrz-mapped")
    rules = xrz.preservation_rules(xrz_baseline, permissions(mapped, "vendor_xrz_prop"))
    platform.write_text(platform.read_text().rstrip("\n") + f"\n\n; {xrz.MARKER}\n" +
                        "\n".join(rules) + "\n")
    property_contexts.write_text(xrz.add_property_contexts(property_contexts.read_text(), others))
    ext.write_bytes(phh.reduce_policy(ext.read_bytes()))
    for source, destination in (
        (platform, f"{image.POLICY}/plat_sepolicy.cil"),
        (mapping, xrz.MAPPING),
        (file_contexts, f"{image.POLICY}/plat_file_contexts"),
        (property_contexts, xrz.PLAT_CONTEXTS),
        (ext, phh.EXT_POLICY),
        (digest(), f"{image.POLICY}/plat_sepolicy_and_mapping.sha256"),
        (ROOT / "tools/ir/hibreak-ir-hal.rc", "system/etc/init/hibreak-ir-hal.rc"),
    ):
        install(source, destination)
    install(hal, "system/lib64/consumerir.hxd.so", label="u:object_r:hibreak_ir_hal_file:s0")
    validate_rebuild(target, vendor, gsi, "base")

    command = [compiler, "-m", "-M", "true", "-G", "-c", "30",
               *map(str, inputs), "-o", str(work / "baseline.policy"),
               "-f", str(work / "baseline.contexts")]
    if parallel_compile:
        baseline_conflicts = compile_pair(command)
    else:
        baseline_conflicts = neverallow_failures(subprocess.run(command, capture_output=True))
        image.run(*command, "-N")
    ordinary = sum(block.startswith("neverallow ") for block in baseline_conflicts)
    if (ordinary, len(baseline_conflicts) - ordinary) != (371, 15):
        raise ValueError("Unexpected reduced GSI/vendor neverallow diagnostics")
    before_bridge = SELinuxPolicy(str(work / "baseline.policy"))
    removed_xrz = xrz_baseline - permissions(before_bridge, "vendor_xrz_prop")
    if any(source != "phhsu_daemon" for source, _, _ in removed_xrz):
        raise ValueError(f"PHH reduction removed non-PHH XRZ access: {sorted(removed_xrz)}")
    xrz_baseline -= removed_xrz
    xrz.validate_xrz_policy(before_bridge, xrz_baseline)
    old_debugfs = {p for p in permissions(before_bridge, "debugfs") if p[1] == "file"}
    for node in eink_bridge.NODES:
        matches = [r for r in before_bridge.genfscons() if r.fs == "debugfs" and
                   (str(r.path) == node or node.startswith(str(r.path).rstrip("/") + "/"))]
        if not matches or str(max(matches, key=lambda r: len(str(r.path))).context.type_) != "debugfs":
            raise ValueError(f"Expected generic debugfs baseline for {node}")
    property_contexts.write_text(eink_bridge.add_contexts(property_contexts.read_text(), others))
    platform.write_text(platform.read_text().rstrip("\n") + "\n\n" +
                        (ROOT / "tools/display/hibreak-init-eink-bridge.cil").read_text())
    for source, destination in (
        (platform, f"{image.POLICY}/plat_sepolicy.cil"),
        (property_contexts, xrz.PLAT_CONTEXTS),
        (digest(), f"{image.POLICY}/plat_sepolicy_and_mapping.sha256"),
        (ROOT / "tools/display/hibreak-init-eink-bridge.rc", "system/etc/init/hibreak-init-eink-bridge.rc"),
    ):
        install(source, destination)
    validate_rebuild(target, vendor, gsi, "bridge")
    bridge_policy = compile_runtime("bridge")
    bridge_permissions = permissions(bridge_policy, migration.BRIDGE_TYPE)
    sysfs_file = {p for p in permissions(bridge_policy, "sysfs") if p[1] == "file"}
    sysfs_xperms = migration.extended_file_permissions(bridge_policy, "sysfs", TERuleQuery, RuleNotConditional)
    for node in migration.FRONTLIGHT_PATHS:
        matches = [r for r in bridge_policy.genfscons() if r.fs == "sysfs" and
                   (str(r.path) == node or node.startswith(str(r.path).rstrip("/") + "/"))]
        if not matches or str(max(matches, key=lambda r: len(str(r.path))).context.type_) != "sysfs":
            raise ValueError(f"Expected generic sysfs baseline for {node}")
    entries = parse_contexts(xrz.PLAT_CONTEXTS, property_contexts.read_text())
    for name, text in others:
        entries.extend(parse_contexts(name, text))
    migration.validate_bridge_contexts(entries)
    additions = (ROOT / "tools/display/hibreak-eink-control-property-contexts").read_text()
    migration.control_contexts(entries, additions)
    destination_types = {resolve_context(name, entries).label.split(":")[2]
                         for name in migration.DESTINATIONS.values()}
    baseline_permissions = {name: permissions(bridge_policy, name) for name in destination_types}
    candidate_cil = "\n".join((ROOT / "tools/display" / name).read_text() for name in (
        "hibreak-eink-candidate.cil", "hibreak-eink-bridge-client.cil", "hibreak-eink-runtime.cil"))
    platform.write_text(platform.read_text() + "\n\n" + candidate_cil)
    preliminary = compile_runtime("frontlight")
    current = {p for p in permissions(preliminary, migration.FRONTLIGHT_TYPE) if p[1] == "file"}
    rules = migration.frontlight_preservation_rules(sysfs_file, current)
    platform.write_text(platform.read_text() + "\n" + "\n".join(rules) + "\n")
    original_system = permissions(preliminary, "system_prop")
    property_contexts.write_text(property_contexts.read_text() + "\n" + additions)
    eink_migration.prepare_file_contexts(file_contexts)
    for source, destination in (
        (platform, f"{image.POLICY}/plat_sepolicy.cil"),
        (property_contexts, xrz.PLAT_CONTEXTS),
        (file_contexts, eink_migration.FILE_CONTEXTS),
        (digest(), f"{image.POLICY}/plat_sepolicy_and_mapping.sha256"),
        (ROOT / "tools/display/hibreak-eink-control.rc", "system/etc/init/hibreak-eink-control.rc"),
        (ROOT / "tools/display/hibreak-eink-migration.rc", eink_migration.INIT_PATH),
    ):
        install(source, destination)
    install(daemon, eink_migration.EXEC_PATH, "0100755", eink_migration.EXEC_CONTEXT)
    validate_rebuild(target, vendor, gsi, "daemon")

    property_contexts.write_text(display_migration.add_contexts(property_contexts.read_text(), others))
    init = image.extract(target, display_migration.INIT_PATH, work / "display.rc")
    init.write_text(display_migration.migrate_init(init.read_text()))
    aod = image.extract(target, display_migration.AOD_PATH, work / "aod.sh")
    aod.write_text(display_migration.migrate_aod(aod.read_text()))
    image.run("sh", "-n", str(aod))
    platform.write_text(platform.read_text().rstrip("\n") + "\n\n" +
                        (ROOT / "tools/display/hibreak-display-migration.cil").read_text())
    for source, destination in (
        (platform, f"{image.POLICY}/plat_sepolicy.cil"),
        (property_contexts, xrz.PLAT_CONTEXTS),
        (digest(), f"{image.POLICY}/plat_sepolicy_and_mapping.sha256"),
        (init, display_migration.INIT_PATH),
    ):
        install(source, destination)
    install(aod, display_migration.AOD_PATH, "0100755")

    input_hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs]
    return (files, inputs, input_hashes, baseline_conflicts, xrz_baseline, old_debugfs,
            baseline_permissions, bridge_permissions, sysfs_file, sysfs_xperms, original_system, xrz)


def verify(target, vendor, compiler, work, prepared, *, parallel_compile):
    from setools import SELinuxPolicy

    (files, inputs, input_hashes, baseline, xrz_baseline, old_debugfs, baseline_permissions,
     bridge_permissions, sysfs_file, sysfs_xperms, original_system, xrz) = prepared
    migration = eink_migration.migration
    directory = "system/priv-app/EinkSettings"
    stat = image.run("debugfs", "-R", f"stat {directory}", str(target)).stdout.decode()
    if "Mode:  0755" not in stat or "User:     0   Group:     0" not in stat or SYSTEM not in stat:
        raise ValueError(f"Final image directory metadata mismatch: {directory}")
    for destination, (expected_hash, mode, label) in files.items():
        (work / "final-file").unlink(missing_ok=True)
        extracted = image.extract(target, destination, work / "final-file")
        if hashlib.sha256(extracted.read_bytes()).hexdigest() != expected_hash:
            raise ValueError(f"Final image content mismatch: {destination}")
        stat = image.run("debugfs", "-R", f"stat {destination}", str(target)).stdout.decode()
        if f"Mode:  {mode}" not in stat or "User:     0   Group:     0" not in stat or label not in stat:
            raise ValueError(f"Final image metadata mismatch: {destination}")

    for path in inputs:
        path.unlink()
    (work / "version").unlink()
    _, final_inputs = extract_policy_inputs(target, vendor, work, allow_existing_ir=True)
    if final_inputs != inputs:
        raise ValueError("Final policy input list differs from prepared policy")
    if [hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs] != input_hashes:
        raise ValueError("Final policy inputs differ from prepared policy")
    expected_digest = eink_migration.policy_digest(inputs, vendor, work).read_text()
    actual_digest = image.extract(target, f"{image.POLICY}/plat_sepolicy_and_mapping.sha256",
                                  work / "final-digest").read_text()
    if expected_digest != actual_digest:
        raise ValueError("Final policy digest does not match installed policy")
    probe = work / "final-probes.cil"
    types = ("vendor_xrz_prop", "hibreak_eink_control_prop", "hibreak_eink_exec",
             "hibreak_display_state_prop")
    probe.write_text("".join(
        f'(filecon "/__hibreak_final_probe_{index}" file (u object_r {name} ((s0) (s0))))\n'
        for index, name in enumerate(types)))
    command = [compiler, "-m", "-M", "true", "-G", "-c", "30",
               *map(str, inputs), "-o", str(work / "final.policy"), "-f", str(work / "final.contexts")]
    runtime = [*command, str(probe), "-N"]
    if parallel_compile:
        conflicts = compile_pair(command, runtime)
    else:
        conflicts = neverallow_failures(subprocess.run(command, capture_output=True))
        image.run(*runtime)
    validate_final_conflicts(baseline, conflicts)
    contexts = (work / "final.contexts").read_text()
    for name in types:
        if f"u:object_r:{name}:s0" not in contexts:
            raise ValueError(f"Compiler did not validate context: {name}")
    candidate = SELinuxPolicy(str(work / "final.policy"))
    xrz.validate_xrz_policy(candidate, xrz_baseline)
    eink_bridge.validate_bridge_policy(candidate, old_debugfs, enforcing=True)
    migration.validate_candidate_policy(candidate, baseline_permissions, bridge_permissions,
                                        sysfs_file, sysfs_xperms, True, True, display_migrated=True)
    display_migration.validate_display_policy(candidate, original_system)
    print(f"Final combined policy validated; {len(conflicts)} existing diagnostics, none added.")
