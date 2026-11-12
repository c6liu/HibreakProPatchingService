"""Prepare and validate the enforcing display/AOD helper migration."""

from collections import Counter
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
from tools.hibreak import image
from tools.hibreak.policy import compile_pair, neverallow_failures, prepare_ir_policy
from tools.hibreak.properties import effective_permissions, parse_contexts, resolve_context

from tools.hibreak import eink_migration as eink_image

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


def validate_display_policy(candidate, original_system):
    from setools import TERuleQuery
    from setools.exception import RuleNotConditional

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


def prepare(source, vendor, work, compiler, *, parallel_compile=False):
    from setools import SELinuxPolicy, TERuleQuery
    from setools.exception import RuleNotConditional

    diagnostics = []
    platform, _, inputs = prepare_ir_policy(source, vendor, work, compiler, allow_existing_ir=True,
                                            diagnostics_out=diagnostics, parallel_compile=parallel_compile)
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
    baseline = diagnostics[0]
    original_system = effective_permissions(baseline_policy, "system_prop", TERuleQuery, RuleNotConditional)
    platform.write_text(platform.read_text().rstrip("\n") + "\n\n" +
                        (DISPLAY / "hibreak-display-migration.cil").read_text())
    probe = work / "display-context-probe.cil"
    probe.write_text('(filecon "/__hibreak_display_context_probe" file '
                     '(u object_r hibreak_display_state_prop ((s0) (s0))))\n')
    if parallel_compile:
        changed = compile_pair(command, [*command, str(probe), "-N"])
    else:
        changed = neverallow_failures(subprocess.run(command, capture_output=True))
    if changed - baseline:
        raise ValueError("Display helper policy changes neverallow diagnostics:\n" +
                         "\n".join(sorted(changed - baseline)))
    if not parallel_compile:
        image.run(*command, str(probe), "-N")
    if STATE_LABEL not in (work / "display.contexts").read_text():
        raise ValueError("Compiler did not validate display property context")
    candidate = SELinuxPolicy(str(work / "display.policy"))
    validate_display_policy(candidate, original_system)
    print(f"Policy: {len(baseline)} existing diagnostic blocks; none added "
          f"({dict(Counter(block.split()[0] for block in baseline))}).", flush=True)
    digest = eink_image.policy_digest(inputs, vendor, work)
    return platform, contexts, init, aod, digest
