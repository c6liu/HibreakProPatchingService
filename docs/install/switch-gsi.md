# Switching GSIs

**Plan to erase all data.** Back up personal files and download/check a
prebuilt image, or build the desired GSI.
If slot A is already prepared, its vbmeta is configured and its stock
`product`/`system_ext` are already deleted, do not repeat those operations.
Set `IMAGE` to the new final image, then:

```bash
adb reboot fastboot
fastboot getvar is-userspace
fastboot getvar current-slot
tools/flash-system.sh "$IMAGE" a --wipe-data
```

Expect `yes` and `a`. Inspect the preview, then execute:

```bash
tools/flash-system.sh "$IMAGE" a --wipe-data --flash
```

Without a wipe, old GSI data can lead to "Can't load Android system" in
recovery. **Press Power after reboot**, then repeat [first-boot setup](first-boot-setup.md).
