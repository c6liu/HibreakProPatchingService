"""Prepare and validate the enforcing e-ink daemon migration."""

import hashlib
import importlib.util
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
from tools.hibreak import image

SPEC = importlib.util.spec_from_file_location("eink_migration", ROOT / "tools/check-eink-migration.py")
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)

DISPLAY = ROOT / "tools/display"
EXEC_PATH = "system/bin/a9_eink_server"
EXEC_CONTEXT = "u:object_r:hibreak_eink_exec:s0"
INIT_PATH = "system/etc/init/a9_eink_gsi.rc"
PROPERTY_CONTEXTS = f"{image.POLICY}/plat_property_contexts"
FILE_CONTEXTS = f"{image.POLICY}/plat_file_contexts"


def prepare_file_contexts(path):
    text = path.read_text()
    if any(line.split("#", 1)[0].split()[:1] == ["/system/bin/a9_eink_server"]
           for line in text.splitlines()):
        raise ValueError("An exact daemon executable file context already exists")
    path.write_text(text.rstrip("\n") + f"\n/system/bin/a9_eink_server {EXEC_CONTEXT}\n")


def policy_digest(inputs, vendor, work):
    digest = hashlib.sha256()
    for path in inputs:
        digest.update(path.read_bytes())
    value = digest.hexdigest()
    vendor_digest = image.extract(
        vendor, "/etc/selinux/precompiled_sepolicy.plat_sepolicy_and_mapping.sha256",
        work / "vendor-policy-digest",
    ).read_text().strip()
    if not re.fullmatch(r"[0-9a-fA-F]{64}", vendor_digest) or vendor_digest.lower() == value:
        raise ValueError("Invalid or unchanged vendor precompiled policy digest")
    path = work / "migration-policy-digest"
    path.write_text(value + "\n")
    return path

