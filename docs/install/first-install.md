# First install on slot A

**Destructive: this wipes shared userdata and removes slot A's stock
`product`/`system_ext` partitions.** It is for a first migration from stock,
not an ordinary update. Leave stock slot B unchanged as a possible fallback,
but remember it shares the erased data partition.

Before starting you need: your [stock backup](backup-stock.md), an
[unlocked bootloader](unlock-bootloader.md), and `IMAGE` set to a checked
system image from [Download and check a prebuilt release](download-release.md)
or your [own build](../build/build-image.md#select-and-check-the-final-image).
Run these commands from the repository folder.

## 1. Prepare slot A's verification metadata

Set `BACKUP` to the folder containing your own stock backup files:

```bash
export BACKUP="/path/to/hibreak-backup"
ls -lh "$BACKUP/vbmeta_a.bin" "$BACKUP/vbmeta_system_a.bin" "$BACKUP/vbmeta_vendor_a.bin"
adb reboot bootloader
fastboot devices
```

Check that the phone is listed. Run each command separately and stop on any
failure. These disable verification for the target slot; **do not relock
the bootloader with this custom image**.

```bash
fastboot --disable-verity --disable-verification flash vbmeta_a "$BACKUP/vbmeta_a.bin"
fastboot --disable-verity --disable-verification flash vbmeta_system_a "$BACKUP/vbmeta_system_a.bin"
fastboot --disable-verity --disable-verification flash vbmeta_vendor_a "$BACKUP/vbmeta_vendor_a.bin"
fastboot --set-active=a
fastboot reboot fastboot
```

## 2. Check fastbootd, preview, then flash

**Bootloader fastboot and fastbootd are different modes.** The system image
must be flashed in fastbootd:

```bash
fastboot getvar is-userspace
fastboot getvar current-slot
```

Expect `is-userspace: yes` and `current-slot: a`. Stop if either differs.
Preview first; this command only prints the planned actions:

```bash
tools/flash-system.sh "$IMAGE" a --delete-stock-logical-partitions --wipe-data
```

Only when the image, slot and wipe are correct, execute:

```bash
tools/flash-system.sh "$IMAGE" a --delete-stock-logical-partitions --wipe-data --flash
```

The helper deletes only slot A's unused logical partitions to make room,
flashes `system_a`, changes to bootloader mode to wipe userdata, and reboots
only after success. It stops on failure. **Do not reboot after a failed flash
or partial partition deletion**; see [Troubleshooting](troubleshooting.md).

**Press Power right after the Bigme logo flashes.**
