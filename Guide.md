# Installing the patched Android 16 GSI on the HiBreak Pro

This guide installs a patched Evolution X 11.11 (Android 16) GSI on the
**black-and-white Bigme HiBreak Pro (MT6877)** with the **stock 3.1.6 vendor**.
It has been tested on one device. It is not for the HiBreak Pro Color or
other firmware. For details and evidence see [Findings](docs/FINDINGS.md).

The image already includes the display fixes, ADB from first boot, the E-Ink
app and daemon, and the AOD fix. You do **not** need root, Magisk, Phh Treble
settings, a screen-mirroring app or manual SurfaceFlinger commands.

> **Press Power after every restart.** Every time the phone restarts or powers
> up, press the Power button once **right after the Bigme logo flashes**.
> Otherwise it can go back to a powered-off state. This is a known issue and is
> not fixed.

## What you need

- A Linux PC with `adb`, `fastboot` and the build dependencies from
  [Building](docs/BUILDING.md).
- A good USB data cable, plugged directly into the PC.
- The bootloader unlocked (step 2).
- A full backup of your phone (step 1). Its `vbmeta` images are needed later.

Commands run on the PC from this repository's folder unless stated otherwise.

## 1. Back up the phone

Back up personal files first. Installing wipes the phone.

Make a partition backup with [mtkclient](https://github.com/bkerler/mtkclient).
Power off and unplug the phone, start the command, then connect the phone as
mtkclient tells you:

```sh
python mtk.py rl hibreak-backup --skip=userdata
```

Keep this folder safe. It is your recovery copy and contains
`vbmeta_a.bin`, `vbmeta_system_a.bin` and `vbmeta_vendor_a.bin`, used in
step 4. Do not use vbmeta images from another firmware version.

## 2. Unlock the bootloader

This erases the phone. On the phone, enable **Developer options**, then turn on
**OEM unlocking** and **USB debugging**. Then:

```sh
adb reboot bootloader
fastboot flashing unlock
```

Confirm on the phone and let it reboot.

## 3. Build the image

Follow [Building](docs/BUILDING.md) steps 1–3. The result is
`build/HiBreakPro.img`.

## 4. First install (slot A)

These commands wipe the phone's data. Stock Android on slot B is not touched
and remains a fallback (but shares the same, wiped, user data).

In **bootloader** mode, flash slot A's vbmeta from your backup with
verification disabled, and make slot A active:

```sh
adb reboot bootloader
B=/path/to/hibreak-backup
fastboot --disable-verity --disable-verification flash vbmeta_a "$B/vbmeta_a.bin"
fastboot --disable-verity --disable-verification flash vbmeta_system_a "$B/vbmeta_system_a.bin"
fastboot --disable-verity --disable-verification flash vbmeta_vendor_a "$B/vbmeta_vendor_a.bin"
fastboot --set-active=a
fastboot reboot fastboot
```

Now in **fastbootd** (`fastboot getvar is-userspace` says `yes`), check the
slot, make room for the GSI and flash it:

```sh
fastboot getvar current-slot          # must say a
fastboot delete-logical-partition product_a
fastboot delete-logical-partition system_ext_a
fastboot -S 64M flash system_a build/HiBreakPro.img
```

The GSI does not use the stock `product` and `system_ext`; without deleting
them the image does not fit. If the flash fails, see
[Troubleshooting](#troubleshooting) and **do not reboot** until it succeeds.

Wipe data from **bootloader** mode (fastbootd cannot wipe on this phone) and
start Android:

```sh
fastboot reboot bootloader
fastboot -w
fastboot reboot
```

**Press Power right after the Bigme logo flashes.**

## 5. First-boot setup

1. Complete Android setup. The screen works on first boot; no extra steps.
2. Open **E-Ink Settings**. Enable the accessibility service and allow
   **Display over other apps** when asked.
3. Double-press the E-Ink button to open the refresh menu. Modes are
   **HD, Regal, Fast, Extreme, Hyper**. By default each app remembers its own
   mode.
4. Optional, in E-Ink Settings:
   - Set separate single/double/long-press actions for the top and bottom
     buttons, including screen-off actions.
   - Turn **Invert colours on Always-On Display** on or off.
   - **Disable Per-App Refresh Mode** to use one mode everywhere.

ADB works from the first boot. Accept the authorization prompt on the phone.

## Updating to a newer build

Same GSI, newer patched image: no wipe, no vbmeta, apps and settings are kept.

```sh
adb reboot fastboot
tools/flash-system.sh build/HiBreakPro-new.img a --flash
```

The helper checks fastbootd and the slot, flashes `system_a` and reboots only
if the flash succeeded. **Press Power right after the Bigme logo flashes.**

The E-Ink app is a persistent system app, so `adb install` cannot update it.
Updates always come through a new image.

## Troubleshooting

- **Phone turns off after a restart:** press Power right after the Bigme logo
  flashes, every time.
- **`reap_urb` / `Protocol error` while flashing:** the USB transfer failed and
  `system_a` may be incomplete. Stay in fastbootd, reconnect (direct port,
  different cable) and run the same flash again. Do not reboot or wipe first.
  `Invalid sparse file format at header magic` on its own is harmless.
- **Recovery says "Can't load Android system" after a first install:** choose
  **Factory data reset**.
- **Screen problems or app controls not working:** collect diagnostics and see
  [Findings](docs/FINDINGS.md):

  ```sh
  tools/collect-diagnostics.sh build/diagnostics
  ```

- **Go back to stock:** from bootloader mode run `fastboot --set-active=b` and
  `fastboot reboot`. The data partition is shared, so stock may need a factory
  reset. For a full restore, write back your mtkclient backup.

## Sources

- [vbbot's HiBreak Pro GSI notes](https://vbh.ai/hibreak-pro-gsi-release/) and
  [Android 15 GSI guide](https://vbh.ai/hibreak-pro-guide-4-flashing-the-android-15-gsi/)
- [Unlocking the HiBreak Pro](https://vbh.ai/unlocking-the-bootloader-and-rooting-the-hibreak-pro/)
- [EvoX Treble releases](https://github.com/Doze-off/EvoX_treble/releases)
- [HiBreak Pro XDA thread](https://xdaforums.com/t/bigme-hibreak-pro-dimensity-900-mt6877-e-ink-phone.4723924/)
