# Setting up the HiBreak Pro

This is a condensed, independently written walkthrough of the HiBreak Pro
guides and community references linked at the end. Read the original posts
before flashing anything. The debloat and DNS steps work on stock firmware;
unlocking, rooting, firmware recovery, and installing a GSI are optional and
progressively riskier. Commands below are for a host terminal unless explicitly
marked as device shell commands.

**Before you start:** Back up your files and keep a copy of the exact stock
firmware for your device. Unlocking the bootloader and `fastboot -w` erase user
data. Flashing the wrong image or partition can leave the phone unbootable.
Install Android platform-tools (`adb` and `fastboot`) and working USB drivers on
your computer. Check that the phone is detected at each stage; never proceed
with a flash command if it is not.

## 1. Debloat stock firmware and set up Private DNS

On the phone, open **Settings > More Settings > About phone** and tap the build
number six times. Under **More Settings > System > Developer Options**, enable
USB debugging. Connect the phone, approve the debugging prompt, then check:

```sh
adb devices
```

To disable an unwanted app for the main user without deleting its APK, run
`adb shell pm disable-user --user 0 PACKAGE` with one package name at a time.
The first guide identifies these candidates:

```text
com.xrz.ai                 com.xrz.dictapp          com.b300.xrz.web
com.xrz.soundrecord        com.xrz.voice.text       com.xrz.scandoc
com.xrz.video              com.xrz.bookmall         com.xrz.bookself
com.xrz.xreaderV3          com.xrz.btranslate       com.xrz.ebook
com.ebook.wifitransferbook com.iflytek.speechcloud com.socialnmobile.colordict
com.test.logcollect        com.xsyt.faceregister
```

Only disable packages you do not need; features may depend on them. In
particular, **do not disable `com.example.test`** if you use the Calendar: the
original guide reports that doing so breaks it. To undo a disable, use
`adb shell pm enable PACKAGE`.

For DNS filtering, create a [NextDNS](https://nextdns.io/) configuration and
copy its **DNS-over-TLS/QUIC** hostname (ending in `.dns.nextdns.io`). The
original guide suggests adding `qq.com` to its denylist, plus the EasyList
China blocklist and Huawei/Xiaomi native tracking protection. Those filters
are optional and may block services you use. On the phone, choose **Settings >
More Settings > Network & Internet > Private DNS > Private DNS provider
hostname**, enter the hostname, and confirm that requests appear in the NextDNS
logs. Private DNS needs a working network and provider; revert to Automatic if
connectivity fails.

## 2. Unlock the bootloader; optionally root stock firmware

In Developer Options enable **OEM unlocking**. Back up your data first: the
unlock confirmation factory-resets the phone. With USB debugging authorized:

```sh
adb reboot bootloader
fastboot devices
fastboot flashing unlock
```

Confirm the unlock on the phone, then reboot and complete setup. The source
also mentions `fastboot flashing unlock_critical`, but says it is not required;
do not unlock critical partitions unless your specific flashing procedure
needs it.

For root, use a boot image **from the exact firmware version currently on your
phone**. Follow [mtkclient's setup instructions](https://github.com/bkerler/mtkclient),
power off the phone, leave the USB cable connected to the phone, hold both
volume buttons, and connect the cable to the computer. In the mtkclient GUI,
read `boot_a` to a `boot_a.bin` file, disconnect, then hold Power to restart.
The original post also offers a prepatched image, but a mismatched boot image
can prevent booting; patching your own is safer.

Install [Magisk](https://github.com/topjohnwu/Magisk/releases) on the phone,
copy `boot_a.bin` to it, and use Magisk's **Select and Patch a File** option.
Copy the patched image from the phone's Download folder back to the computer.
Once `fastboot devices` detects the phone in bootloader mode, flash it as in
the source guide (replace the placeholder with your actual file path):

```sh
adb reboot bootloader
fastboot flash boot_a /path/to/magisk_patched.img
fastboot flash boot_b /path/to/magisk_patched.img
fastboot reboot
```

Check Magisk's installed status after reboot. Do not reuse this patched image
after changing firmware: extract and patch a boot image from the new build.

## 3. Optional: manually install stock firmware 1.9.6

This is a **recovery route**, not the normal update path. Use the phone's
supported updater when it works. The linked post describes firmware **1.9.6**
as of April 2025; check your current version and image compatibility rather
than assuming this is still the latest release.

Install Python, [mtkclient](https://github.com/bkerler/mtkclient), and
[payload_dumper](https://github.com/vm03/payload_dumper), and obtain the
[1.9.6 stock OTA and super image](https://mega.nz/folder/di5mTb5J#twNBH89T59wMpfmIarqgTQ)
linked by the author. Extract the OTA archive, then extract its `payload.bin`
from the payload_dumper directory:

```sh
python payload_dumper.py /path/to/payload.bin
```

The extracted partition images appear in `output/`; check whether the package
contains individual `vbmeta`, `vbmeta_system`, and `vbmeta_vendor` images. The
XDA thread's [post #66](https://xdaforums.com/t/bigme-hibreak-pro-dimensity-900-mt6877-e-ink-phone.4723924/page-4#post-90233941)
also shares a BigMe stock-recovery package identified as B651 1.9.6
(2025-04-03), plus SP Flash Tool resources. Treat it as a recovery option,
not as a source of vbmeta files for every firmware: use those images only if
the installed stock build is exactly compatible. The post's SP Flash Tool
procedure is a full firmware restore and erases data; do not run it just to
extract partition files.

If you need to dump the phone directly, the XDA thread's [opening post](https://xdaforums.com/t/bigme-hibreak-pro-dimensity-900-mt6877-e-ink-phone.4723924/)
describes mtkclient backups and working with slot-specific partitions. Before
attempting this, install the mtkclient Windows drivers/UsbDk or follow its
Linux setup instructions. Seeing a MediaTek USB ID in UsbDk only proves that
Windows enumerated a device; it does not mean mtkclient connected or read
flash. If mtkclient keeps returning USB enumeration or I/O errors, stop
retrying and use a matching stock firmware package or a known-good recovery
method instead.

For a full mtkclient backup, power off and unplug the phone. Start the backup
command from the mtkclient directory, then connect the phone as directed by
the tool:

```sh
python mtk.py rf flash.bin                 # full flash, including userdata (~256 GB)
# OR
python mtk.py rl --skip=userdata out       # partitions without userdata
```

Store the backup securely: a full flash contains personal data. Once the
backup finishes, inspect the actual partition layout:

```sh
python mtk.py printgpt
```

To read only a partition, use mtkclient's `r` command after confirming the
exact partition name in the layout. For example, if the listed partition is
`vbmeta_a`:

```sh
python mtk.py r vbmeta_a vbmeta_a.img
```

Repeat for the other vbmeta partitions that actually appear in the layout,
using a distinct output filename for each. These are examples, not a
substitute for checking the phone's GPT and mtkclient version-specific usage.

Match each extracted image against that layout before writing it. For example,
if `vbmeta_a` and `vbmeta_b` both exist and match the downloaded firmware:

```sh
python mtk.py w vbmeta_a /path/to/vbmeta.img
python mtk.py w vbmeta_b /path/to/vbmeta.img
```

The source notes that `product`, `system`, `system_ext`, and `vendor` are
logical partitions inside `super`; do not try to write them as physical
mtkclient partitions. Instead use the matching `super.bin` supplied alongside
the OTA:

```sh
python mtk.py w super /path/to/super.bin
```

The article does not give a universal list of the other partitions to flash.
Do not guess: compare the extracted images, GPT, and source instructions for
your exact build. Disconnect when done and hold Power until the screen changes.
If you previously rooted the phone, patch the new build's boot image again.

## 4. Optional: flash an Android 16 EvoX Treble GSI

First make a stock backup as described above and unlock the bootloader. The
[Doze-off EvoX Treble releases](https://github.com/Doze-off/EvoX_treble/releases)
currently include an Android 16 QPR2 build (`Evolution X 11.11`, released
2026-09-20). For the HiBreak Pro, select an `arm64-ab` image. The
[2026-09-20 release](https://github.com/Doze-off/EvoX_treble/releases/tag/2026-09-20)
has GAPPS, MICROG, and VANILLA variants; choose the variant you want. Download
and extract the `.img.xz` file to obtain the GSI `.img`.

This is a generic Android 16 GSI, not a HiBreak Pro-specific ROM. The XDA
HiBreak Pro thread contains GSI discussion, but I did not find a verified
report there that this Android 16 EvoX release boots and works correctly on
the HiBreak Pro. Treat it as an experiment, not a confirmed device-compatible
upgrade; preserve a tested route back to the exact stock firmware before
flashing.

You also need `vbmeta.img`, `vbmeta_system.img`, and `vbmeta_vendor.img` from
the **stock firmware currently installed on your phone**. Do not assume
vbmeta images for another firmware build are compatible. This process wipes
data and disables verified boot checks.

The following steps follow the HiBreak Pro-specific Android 15 GSI guide's
partition layout and adapt it to the Android 16 EvoX image. Confirm the
partition names for your phone before flashing; stop if they do not match.
Enter the bootloader, check that fastboot detects the phone, and wipe user
data. From the directory containing the three matching stock vbmeta images,
run:

```sh
adb reboot bootloader
fastboot devices
fastboot -w
fastboot --disable-verity --disable-verification flash vbmeta_a vbmeta.img
fastboot --disable-verity --disable-verification flash vbmeta_b vbmeta.img
fastboot --disable-verity --disable-verification flash vbmeta_system_a vbmeta_system.img
fastboot --disable-verity --disable-verification flash vbmeta_system_b vbmeta_system.img
fastboot --disable-verity --disable-verification flash vbmeta_vendor_a vbmeta_vendor.img
fastboot --disable-verity --disable-verification flash vbmeta_vendor_b vbmeta_vendor.img
fastboot reboot fastboot
fastboot devices
fastboot flash system /path/to/EvoX-GSI.img
fastboot reboot
```

The `system` flash runs in **fastbootd**, not the initial bootloader fastboot
mode. Replace `/path/to/EvoX-GSI.img` with the path to the extracted image.
Do not use generic partition-deletion or resize commands just because another
device's GSI instructions mention them; only follow such steps if they are
confirmed for this phone's partition layout.

These steps install the unmodified EvoX GSI. They do **not** add this
repository's E-Ink app or daemon. The README explains that this repository
does not contain a generic system-image patcher; integration into the EvoX
build or a separately verified patching process is needed to include them.
The EvoX release notes also warn that DSU may fail on some older devices; this
guide uses direct flashing and does not rely on DSU.

On first boot the display may not respond. The HiBreak Pro guide suggests
disabling hardware overlays from Developer Options (a screen-mirroring tool
may help) or trying `adb shell service call SurfaceFlinger 1008 i32 1`.

### E-Ink integration compatibility

The HiBreak Pro guide reports these device nodes for refresh mode and
backlight controls:

```text
/sys/kernel/debug/eink_debug/global_mode
/sys/devices/platform/11d01000.i2c7/i2c-7/7-0036/lm3630a_cold_light
/sys/devices/platform/11d01000.i2c7/i2c-7/7-0036/lm3630a_warm_light
```

The daemon uses matching paths for those controls. However, it also accesses
`/sys/devices/platform/soc/soc:qcom,dsi-display-primary/epd_*` for bitmap
commit, thresholds, and contrast. Those Qualcomm-specific paths are not
documented by the HiBreak Pro guide, so those features are unverified and
likely need device-specific changes. The daemon's force-clear handler is also
empty. Do not assume every setting in the app works on this GSI.

The daemon's SELinux executable label is `phhsu_exec`; confirm that the
selected EvoX image defines a compatible policy and grants the needed
hardware-node access before expecting daemon controls to work. The service,
daemon, and SELinux integration have not been validated against this EvoX
release.

## Sources

1. [Debloating and Private DNS](https://vbh.ai/hibreak-pro-guide-1-debloating-the-hibreak-pro-and-setting-up-private-dns/)
2. [Unlocking and rooting](https://vbh.ai/unlocking-the-bootloader-and-rooting-the-hibreak-pro/)
3. [Manual stock firmware upgrade](https://vbh.ai/hibreak-pro-guide3-an-extremely-rubbish-way-to-upgrade-your-hibreak-pro-to-the-latest-firmware/)
4. [Android 15 GSI flashing on the HiBreak Pro](https://vbh.ai/hibreak-pro-guide-4-flashing-the-android-15-gsi/)
5. [EvoX Treble releases](https://github.com/Doze-off/EvoX_treble/releases)
6. [HiBreak Pro XDA discussion thread](https://xdaforums.com/t/bigme-hibreak-pro-dimensity-900-mt6877-e-ink-phone.4723924/)
7. [XDA post #66: stock recovery resources](https://xdaforums.com/t/bigme-hibreak-pro-dimensity-900-mt6877-e-ink-phone.4723924/page-4#post-90233941)
