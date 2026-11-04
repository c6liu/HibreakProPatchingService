# HiBreak Pro: install a patched Android 16 image

This guide is for the **black-and-white Bigme HiBreak Pro (MT6877)** with
**stock 3.1.6 vendor**. It is **not** for the HiBreak Pro Color.
Keep the stock vendor, boot and kernel; do not install a Color HWC shim.

> **Firmware compatibility:** this is not a universal HiBreak Pro image.
> The documented stock baseline is **3.1.6 /
> `Bigme_HiBreak_V1.0_20260306`**. Older and newer stock firmware are
> untested. An image built/validated against this vendor may fail to boot
> or lose functionality on another version. Do not flash it on a different
> firmware baseline merely because the phone model matches.

The result includes E-Ink settings, the matching display daemon, and AOD fixes.
Optional IR support lets ordinary Android IR apps transmit single NEC/NECext
commands. Root/Magisk is not required. Release images remove `su`, omit
project diagnostic hooks, and do not embed a computer's ADB key.

**What has been tested:** display fixes on LineageOS 23.2 and EvoX 11.11 on
one device; ordinary-app NEC IR on EvoX. The fully patched LineageOS microG
release configuration has not yet been checked on the phone.
See [Findings](docs/research/README.md) for limitations.

> **Before flashing:** back up personal files and the exact stock firmware.
> Unlocking and a first GSI install erase data. Both slots share userdata.
>
> **After every restart:** press Power once **right after the Bigme logo
> flashes**, otherwise the phone may turn off again. This known issue is
> not fixed.

## Use a prebuilt release image

Most users should follow these pages in order. Each one is short and ends
where the next begins.

1. [Prepare your Linux computer](docs/install/prepare-computer.md)
2. [Download and check a prebuilt release](docs/install/download-release.md)
3. [Back up stock firmware](docs/install/backup-stock.md)
4. [Unlock the bootloader](docs/install/unlock-bootloader.md) (first installation only)
5. [First install on slot A](docs/install/first-install.md) (**erases data**)
6. [First-boot setup](docs/install/first-boot-setup.md)

## Build your own image

Only needed if you want to change or rebuild the image yourself. See the
[build guide](docs/build/README.md). It ends with an image; then continue with
steps 3–6 above, using your own image instead of a downloaded one.

## Updating the same GSI

Already running a patched image of the same GSI? Use
[Update the same GSI](docs/install/update.md). It keeps your data.

## Switching GSIs

Changing to a different GSI family **erases all data**. Use
[Switch GSIs](docs/install/switch-gsi.md), not the no-wipe update.

## Troubleshooting

See [Troubleshooting](docs/install/troubleshooting.md). For everything else,
including technical details and research notes, see the
[documentation index](docs/README.md).
