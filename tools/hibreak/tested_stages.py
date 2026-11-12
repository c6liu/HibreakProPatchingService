"""Verify policy-critical inputs for rebuilding the user-tested image pipeline."""

import hashlib
import tempfile
from pathlib import Path

from tools.hibreak import image

GSI_SHA256 = "d25aeac2b42012e76e8f4fd95d69f9e28ceeac64289d85f194d72ef0249374bf"
VENDOR_SHA256 = "6ba5354d8bcd1b1b91cfc79c3cbe148ddd31df706e0aa6c6e03191f9dcff24ff"
COMMON = {
    "system/etc/selinux/mapping/31.0.cil": "ad92fd49cb59230af7c9eade6db3d0194e03939dd0a6a9c6290b08174898c19c",
    "system/etc/selinux/mapping/31.0.compat.cil": "adddc30714cef2ec2beb4eecdc24df86acb145e390a708bd2ae5ac41b6fd7630",
    "system/system_ext/etc/selinux/system_ext_sepolicy.cil": "cfad9916fbc4cfd558505220cef41dde84384fcbcff7e6af906b90fee9e391f0",
    "system/system_ext/etc/selinux/system_ext_property_contexts": "f7653e2a7bba2d6fad3a64bb11a8e9af9970c8bf4d13cece264192dffe2ffac7",
    "system/system_ext/etc/selinux/system_ext_file_contexts": "e1d495cfd906ab09e49b1e9404a0d3418fffd532520e98245a6da2bf04f9c5e6",
    "system/system_ext/etc/selinux/mapping/31.0.cil": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "system/system_ext/etc/selinux/mapping/31.0.compat.cil": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "system/product/etc/selinux/product_sepolicy.cil": "01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b",
    "system/product/etc/selinux/product_property_contexts": "b5c345bdb25d20419eec6d4ce1b4ee417e6c3d872cb1faa10fc7b05f32c2cce8",
    "system/product/etc/selinux/product_file_contexts": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "system/product/etc/selinux/mapping/31.0.cil": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "system/etc/init/hibreak-display.rc": "0f4ecb3176d999d0cdb55de5751f4b6e2293ed04c367505550d7363fc4519299",
    "system/bin/hibreak-aod.sh": "34a2e797b25603db28fe24dd9777a4b5f83faac23ef07677b29df7441c7f94e4",
}
STAGES = {
    "base": {
        "system/etc/selinux/plat_sepolicy.cil": "2861169cc66345af3a419e120722a2da882089c132197a5bdc0cf611e6c36dc1",
        "system/etc/selinux/plat_property_contexts": "eacd9fb872befc051b7ec04a3b98e41af00366983d89e0cb7a29e159ae2de20e",
        "system/etc/selinux/plat_file_contexts": "2a6512f2d8c4ce82f802f3101035a7bdbeca2ea21671fa1fe28f0994f2bcd7e6",
        "system/etc/init/a9_eink_gsi.rc": "ad3fc218f5972616fa02e0f8c3e665db5b25a1faf558f54b62e3d1b6f398d8a4",
    },
    "bridge": {
        "system/etc/selinux/plat_sepolicy.cil": "54708c06c71c3a1cd0d9c00e81f9a6477a0a1d39e638d681bb083289d4993170",
        "system/etc/selinux/plat_property_contexts": "b73c84bac51174f426f5667b1d4f03cd5c3ef1f2395b1cdb55c891e811f9e457",
        "system/etc/selinux/plat_file_contexts": "2a6512f2d8c4ce82f802f3101035a7bdbeca2ea21671fa1fe28f0994f2bcd7e6",
        "system/etc/init/a9_eink_gsi.rc": "ad3fc218f5972616fa02e0f8c3e665db5b25a1faf558f54b62e3d1b6f398d8a4",
        "system/etc/init/hibreak-init-eink-bridge.rc": "6a9f38505d90a655763bcfd44991202ef501130a2fa622ed6cb9a9b297dd6bfe",
    },
    "daemon": {
        "system/etc/selinux/plat_sepolicy.cil": "9d8fb8d2bda2fb8d00ffaf199ad3d48c71dae2bb22df48a79b8848a0b85600d5",
        "system/etc/selinux/plat_property_contexts": "0e8b440c2480d56325db2cb569b8a0592413c0562ecf5ef6577084e97c72f002",
        "system/etc/selinux/plat_file_contexts": "18759464b4e9d6652087a91db4d2ee4bb286e4af85e3eac7a44c7442589d8781",
        "system/etc/init/a9_eink_gsi.rc": "fd6072361487121bd594972d494bd0888b99d9f0d2b273c7d26791dac904ce36",
        "system/etc/init/hibreak-init-eink-bridge.rc": "6a9f38505d90a655763bcfd44991202ef501130a2fa622ed6cb9a9b297dd6bfe",
        "system/etc/init/hibreak-eink-control.rc": "93f9070eb0e7174dc10dd40645598790ed4b0a9ffea2f6d1db56a5c579eb15ff",
    },
}


def validate_metadata(source, stage):
    files = {
        "system/bin/a9_eink_server": ("0755", "hibreak_eink_exec" if stage == "daemon" else "system_file"),
        "system/bin/hibreak-aod.sh": ("0755", "system_file"),
        "system/etc/init/a9_eink_gsi.rc": ("0644", "system_file"),
        "system/etc/init/hibreak-display.rc": ("0644", "system_file"),
    }
    if stage != "base":
        files["system/etc/init/hibreak-init-eink-bridge.rc"] = ("0644", "system_file")
    if stage == "daemon":
        files["system/etc/init/hibreak-eink-control.rc"] = ("0644", "system_file")
    for path, (mode, label) in files.items():
        stat = image.run("debugfs", "-R", f"stat {path}", str(source)).stdout.decode()
        if (f"Mode:  {mode}" not in stat or "User:     0   Group:     0" not in stat
                or f"u:object_r:{label}:s0" not in stat):
            raise ValueError(f"Unverified {stage} image metadata: {path}")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_rebuild(source, vendor, gsi, stage):
    if sha256(gsi) != GSI_SHA256 or sha256(vendor) != VENDOR_SHA256:
        raise ValueError("Enforcing rebuild requires the exact tested GSI and vendor images")
    validate_metadata(source, stage)
    with tempfile.TemporaryDirectory(prefix="hibreak-stage-check-") as directory:
        work = Path(directory)
        if image.image_exists(source, "system/product/etc/selinux/mapping/31.0.compat.cil"):
            raise ValueError(f"Unverified {stage} image component: product mapping compatibility policy")
        for index, (path, expected) in enumerate({**COMMON, **STAGES[stage]}.items()):
            actual = sha256(image.extract(source, path, work / str(index)))
            if actual != expected:
                raise ValueError(f"Unverified {stage} image component: {path}")
