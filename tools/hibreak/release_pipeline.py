"""Apply the release overlays to one private working image."""

import hashlib
import importlib.util
import shutil
import tempfile
import time
from pathlib import Path

from tools.hibreak import image
from tools.hibreak import display_migration, eink_bridge, eink_migration, final_policy
from tools.hibreak.elf import validate_hal_module
from tools.hibreak.tested_stages import validate_rebuild

ROOT = Path(__file__).resolve().parents[2]
SYSTEM = "u:object_r:system_file:s0"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / filename)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def install_files(target, work, files):
    for source, destination, mode, context in files:
        image.install(target, source, destination, mode, context, work)


def build(gsi, output, apk, daemon, vendor, hal, compiler, *, ir, xrz,
          reduction, bridge, enforcing, report, parallel_compile=True, strict_verification=False):
    """Build a release image; output must be a new private temporary path."""
    patch = load("release_patch_gsi", "patch-gsi.py")
    tools = ["debugfs", "e2fsck", "resize2fs", "dumpe2fs", "sha256sum", "python3"]
    if ir or xrz or reduction or bridge or enforcing:
        tools.extend(["cp", compiler])
    if ir:
        tools.append("readelf")
    for tool in tools:
        if not tool or not shutil.which(tool):
            raise ValueError(f"Missing dependency: {tool}")
    for path in (gsi, apk, daemon):
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Missing input: {path}")
    patch.validate_paths((gsi, output, apk, daemon, vendor, hal, ROOT, Path(tempfile.gettempdir())))

    def stage(name, function):
        started = time.monotonic()
        function()
        elapsed = time.monotonic() - started
        report.append({"tool": name, "elapsed_seconds": round(elapsed, 3)})
        print(f"Completed {name} in {elapsed:.1f}s", flush=True)

    stage("patch-gsi.py", lambda: patch.patch_image(
        gsi, output, apk, daemon, None, True, False, finalize=False))
    with tempfile.TemporaryDirectory(prefix="hibreak-release-policy-") as directory:
        root = Path(directory)

        if not strict_verification and all((ir, xrz, reduction, bridge, enforcing)):
            prepared = []
            stage("prepare-combined-policy", lambda: prepared.append(
                final_policy.prepare(output, gsi, vendor, hal, daemon, compiler, root, load,
                                     parallel_compile=parallel_compile)))
            stage("finalize-image", lambda: image.shrink_and_check(output, strict_final=True))
            stage("verify-combined-policy", lambda: final_policy.verify(
                output, vendor, compiler, root, prepared[0], parallel_compile=parallel_compile))
            stage("verify-release", lambda: patch.validate_patched_image(output, None, True, False))
            stage("verify-filesystem", lambda: image.check_final_filesystem(output))
            return
        if not strict_verification and any((ir, xrz, reduction, bridge, enforcing)):
            print("Using per-stage verification for this compatibility feature combination.", flush=True)

        def work(name):
            path = root / name
            path.mkdir()
            return path

        if ir:
            def apply_ir():
                module = load("release_ir", "add-ir-capture-to-gsi.py")
                scratch = work("ir")
                validate_hal_module(hal)
                stock = image.extract(vendor, "/lib64/hw/consumerir.common.so", scratch / "stock-ir.so")
                service = image.extract(vendor, "/etc/init/android.hardware.ir@1.0-service.rc",
                                        scratch / "stock-ir.rc")
                if stock.read_bytes()[:6] != b"\x7fELF\x02\x01" or "class hal" not in service.read_text():
                    raise ValueError("Expected arm64 legacy consumerir.common.so and class-hal IR service")
                platform, contexts, inputs = module.prepare_policy(output, vendor, scratch, compiler, hal=True,
                                                                   parallel_compile=parallel_compile)
                digest = hashlib.sha256()
                for path in inputs:
                    digest.update(path.read_bytes())
                digest_file = scratch / "policy-digest"
                digest_file.write_text(digest.hexdigest() + "\n")
                install_files(output, scratch, (
                    (platform, f"{image.POLICY}/plat_sepolicy.cil", "0100644", SYSTEM),
                    (contexts, f"{image.POLICY}/plat_file_contexts", "0100644", SYSTEM),
                    (digest_file, f"{image.POLICY}/plat_sepolicy_and_mapping.sha256", "0100644", SYSTEM),
                    (hal, "system/lib64/consumerir.hxd.so", "0100644", "u:object_r:hibreak_ir_hal_file:s0"),
                    (ROOT / "tools/ir/hibreak-ir-hal.rc", "system/etc/init/hibreak-ir-hal.rc", "0100644", SYSTEM),
                ))
            stage("add-ir-capture-to-gsi.py", apply_ir)

        if xrz:
            def apply_xrz():
                module = load("release_xrz", "add-xrz-compat-to-gsi.py")
                scratch = work("xrz")
                files = module.prepare_compatibility(output, vendor, scratch, compiler,
                                                     parallel_compile=parallel_compile)
                destinations = (f"{image.POLICY}/plat_sepolicy.cil", module.MAPPING,
                                module.PLAT_CONTEXTS, f"{image.POLICY}/plat_sepolicy_and_mapping.sha256")
                if len(files) != len(destinations):
                    raise ValueError("Expected exactly four XRZ policy inputs")
                install_files(output, scratch, [(f, p, "0100644", SYSTEM) for f, p in zip(files, destinations)])
            stage("add-xrz-compat-to-gsi.py", apply_xrz)

        if reduction:
            def apply_reduction():
                module = load("release_phh", "add-phh-reduction-to-gsi.py")
                scratch = work("phh")
                files = module.prepare_reduction(output, vendor, scratch, compiler,
                                                 parallel_compile=parallel_compile)
                destinations = (module.EXT_POLICY, f"{image.POLICY}/plat_sepolicy_and_mapping.sha256")
                if len(files) != len(destinations):
                    raise ValueError("Expected exactly two PHH policy inputs")
                install_files(output, scratch, [(f, p, "0100644", SYSTEM) for f, p in zip(files, destinations)])
            stage("add-phh-reduction-to-gsi.py", apply_reduction)

        if bridge:
            def apply_bridge():
                module = eink_bridge
                scratch = work("bridge")
                validate_rebuild(output, vendor, gsi, "base")
                files = module.prepare_bridge(output, vendor, scratch, compiler,
                                              parallel_compile=parallel_compile)
                path = "system/etc/init/hibreak-init-eink-bridge.rc"
                if image.image_exists(output, path):
                    raise ValueError("Bridge init script already present")
                install_files(output, scratch, (
                    (files[0], f"{image.POLICY}/plat_sepolicy.cil", "0100644", SYSTEM),
                    (files[1], module.PLAT_CONTEXTS, "0100644", SYSTEM),
                    (files[2], f"{image.POLICY}/plat_sepolicy_and_mapping.sha256", "0100644", SYSTEM),
                    (module.DISPLAY / "hibreak-init-eink-bridge.rc", path, "0100644", SYSTEM),
                ))
            stage("eink-bridge", apply_bridge)

        if enforcing:
            def apply_daemon():
                module = eink_migration
                scratch = work("eink")
                validate_rebuild(output, vendor, gsi, "bridge")
                platform, properties, inputs = module.migration.validate(
                    output, vendor, scratch, compiler, True, True, parallel_compile=parallel_compile)
                contexts = scratch / "contexts"
                module.prepare_file_contexts(contexts)
                digest = module.policy_digest(inputs, vendor, scratch)
                for path in (module.EXEC_PATH, module.INIT_PATH):
                    if not image.image_exists(output, path):
                        raise ValueError(f"Missing existing daemon component: {path}")
                control = "system/etc/init/hibreak-eink-control.rc"
                if image.image_exists(output, control):
                    raise ValueError("Candidate control init script already present")
                install_files(output, scratch, (
                    (platform, f"{image.POLICY}/plat_sepolicy.cil", "0100644", SYSTEM),
                    (properties, module.PROPERTY_CONTEXTS, "0100644", SYSTEM),
                    (contexts, module.FILE_CONTEXTS, "0100644", SYSTEM),
                    (digest, f"{image.POLICY}/plat_sepolicy_and_mapping.sha256", "0100644", SYSTEM),
                    (module.DISPLAY / "hibreak-eink-control.rc", control, "0100644", SYSTEM),
                    (module.DISPLAY / "hibreak-eink-migration.rc", module.INIT_PATH, "0100644", SYSTEM),
                    (daemon, module.EXEC_PATH, "0100755", module.EXEC_CONTEXT),
                ))
            stage("eink-migration", apply_daemon)

            def apply_display():
                module = display_migration
                scratch = work("display")
                validate_rebuild(output, vendor, gsi, "daemon")
                platform, contexts, init, aod, digest = module.prepare(
                    output, vendor, scratch, compiler, parallel_compile=parallel_compile)
                install_files(output, scratch, (
                    (platform, f"{image.POLICY}/plat_sepolicy.cil", "0100644", SYSTEM),
                    (contexts, module.PROPERTY_CONTEXTS, "0100644", SYSTEM),
                    (digest, f"{image.POLICY}/plat_sepolicy_and_mapping.sha256", "0100644", SYSTEM),
                    (init, module.INIT_PATH, "0100644", SYSTEM),
                    (aod, module.AOD_PATH, "0100755", SYSTEM),
                ))
            stage("display-migration", apply_display)

    stage("finalize-image", lambda: image.shrink_and_check(output, strict_final=True))
