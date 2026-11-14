# Updating the same GSI

Back up personal files. Download and check a new prebuilt image using the
[prebuilt route](download-release.md), or [build one](../build/README.md) using the **same signing key**. For prebuilt
updates, check the release's upgrade instructions and signing compatibility;
do not assume a prebuilt release can update a self-built or differently
signed image without app-data cleanup or a clean install.
Set `IMAGE` to that new file. Do not reuse the first-install deletion/wipe
flags or reflash vbmeta:

```bash
adb reboot fastboot
fastboot getvar is-userspace
fastboot getvar current-slot
tools/device/flash-system.sh "$IMAGE" a
```

Expect `yes` and slot `a`, then execute:

```bash
tools/device/flash-system.sh "$IMAGE" a --flash
```

This preserves userdata; it does not guarantee every upstream GSI update is
compatible. **Press Power after reboot.** The Eink Settings APK is a persistent
system app, so update it through a new image, not `adb install`.
The installed app folder is now `/system/priv-app/EinkSettings/`. When
repatching an older image, the patcher removes the previous `HiBreakEink`
folder so the image does not contain two APKs in those locations.

## One-time app and daemon identity migration

The identity-renaming release changes the app package to
`com.lmqr.eink_settings` and renames the daemon service to `eink_server`.
Build this release from the original unmodified GSI, not an older patched
image, to avoid retaining obsolete daemon binaries or init services.
App settings, side-key assignments, permissions, and accessibility bindings
from the previous package do not migrate automatically. After flashing,
open **Eink Settings**, enable **Eink Accessibility Service**, check overlay
access, and configure your preferences again. Keep using the same signing
key for subsequent releases of the new package. Deploy the app and daemon
in the same image.
