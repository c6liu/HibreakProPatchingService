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
compatible. **Press Power after reboot.** The E-Ink APK is a persistent
system app, so update it through a new image, not `adb install`.
