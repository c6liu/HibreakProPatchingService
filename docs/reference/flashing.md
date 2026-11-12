# Flashing helper reference

**Back up the exact stock firmware and personal data.** Unlocking erases data.
The scripts do not unlock, modify vbmeta, or enlarge super. The flash helper
leaves logical partitions alone unless explicitly asked to delete
`product_<slot>` and `system_ext_<slot>` with
`--delete-stock-logical-partitions`. See [Guide.md](../../Guide.md) for first
migration steps. Use the **stock vendor**, not the experimental HWC shim.
Never flash vendor/boot images from a different firmware or blindly copy
another user's partition commands.

Preview first (no device commands executed):

```bash
tools/device/flash-system.sh build/HiBreakPro.img a
```

If slot A is the intended, prepared slot:

```bash
adb reboot fastboot
tools/device/flash-system.sh build/HiBreakPro.img a --flash
```

For a **first migration from official stock firmware** that requires a factory
reset, preview the destructive action first:

```bash
tools/device/flash-system.sh build/HiBreakPro.img a --wipe-data
```

For the first GSI migration, also pass `--delete-stock-logical-partitions` to
remove the unused `product` and `system_ext` logical partitions for that slot;
this is needed to make room for the GSI. The option is destructive, so inspect
the preview before executing. For example:

```bash
tools/device/flash-system.sh build/HiBreakPro.img a \
  --delete-stock-logical-partitions --wipe-data
tools/device/flash-system.sh build/HiBreakPro.img a \
  --delete-stock-logical-partitions --wipe-data --flash
```

With the deletion flag, the helper deletes `product_<slot>` and
`system_ext_<slot>` in fastbootd before flashing the selected system slot. It
stops if either deletion fails; if only the first deletion succeeds, do not
reboot until the partition state is resolved. It then reboots to the
bootloader (fastbootd cannot wipe userdata on this phone), confirms it is no
longer in fastbootd, and runs `fastboot -w` before rebooting. This erases
shared userdata—including installed apps, settings, and personal files—and
affects both slots. The option is never implicit; omit `--wipe-data` when
updating the same GSI to preserve data.
On successful wipes, the helper filters fastboot's notices that optional
`cache` or `metadata` partitions are absent; other output is preserved, and all
wipe output is shown if the wipe fails.
Back up anything important before using it. A failed system flash does not run
the wipe; if the wipe itself fails, the helper stops without rebooting.

> **Press Power right after the Bigme logo flashes** on every restart or
> power-up, otherwise the phone can go back to powered-off. Not fixed.

The flashing helper checks that the phone is in fastbootd on slot A, checks the ext4 image, flashes
only the requested system slot, and reboots only after a successful flash. It
does not switch slots. The optional wipe sequence above is only for a planned
fresh migration; the two slots share userdata.

The helper uses fastboot's default sparse-transfer size. If flashing fails
with `reap_urb` / `Protocol error`, the USB transfer failed and the system
partition may be incomplete. **Do not reboot or wipe.** Keep the phone in
fastbootd, reconnect USB if necessary, check `fastboot devices`, and retry the
complete flash. Try a direct USB port and a known-good data cable if the
failure repeats. The helper stops without rebooting after a failed flash.

`Invalid sparse file format at header magic` can appear when fastboot reads
the raw ext4 image before converting it into sparse transfers; it alone does
not indicate corruption. The complete flash must finish successfully before
rebooting.
