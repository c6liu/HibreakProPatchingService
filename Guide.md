# HiBreak Pro: build and install a patched Android 16 image

This guide is for the **black-and-white Bigme HiBreak Pro (MT6877)** with
**stock 3.1.6 vendor**. It is **not** for the HiBreak Pro Color.
Keep the stock vendor, boot and kernel; do not install a Color HWC shim.

The result includes E-Ink settings, the matching display daemon, and AOD fixes.
Optional IR support lets ordinary Android IR apps transmit single NEC/NECext
commands. Root/Magisk is not required. The release commands below remove
`su`, omit project diagnostic hooks, and do not embed a computer's ADB key.

**What has been tested:** display fixes on LineageOS 23.2 and EvoX 11.11 on
one device; ordinary-app NEC IR on EvoX. The fully patched LineageOS microG
release configuration has not yet been checked on the phone.
See [Findings](docs/FINDINGS.md) for limitations.

> **Before flashing:** back up personal files and the exact stock firmware.
> Unlocking and a first GSI install erase data. Both slots share userdata.
>
> **After every restart:** press Power once **right after the Bigme logo
> flashes**, otherwise the phone may turn off again. This known issue is
> not fixed.

## Choose your route

- **New installation:** follow sections 1 through 8.
- **Only building an image:** follow sections 1, 2, 5 and 6. IR also needs
  the stock vendor image described in section 3. Do not run section 7.
- **Updating the same GSI:** build, then use [Updating](#updating-the-same-gsi).
- **Moving from EvoX to LineageOS:** use
  [Switching GSIs](#switching-gsis-for-example-evox-to-lineageos), not the
  no-wipe update instructions.

## 1. Prepare your Linux computer

Use an x86-64 Linux PC, a good USB data cable and a direct USB port.
Allow **at least 40 GiB free**, more for multiple full images/backups.
Keep another copy of the backup on a different drive.

### How to use the commands

- Run one command at a time. **Stop if it reports an error**; later commands
  do not repair earlier failures.
- Copy only the text inside command blocks, not a terminal's `$` prompt.
- Replace example paths such as `/path/to/hibreak-backup` with your own.
- Commands run on the PC, not in `adb shell`. Do not run builds with `sudo`.
  Only package installation and USB-rule setup need administrator access.
- Do **not** paste `set -euo pipefail` into your terminal. The project's
  scripts already stop on errors without changing your interactive shell.
- Variables set with `export` last only in that terminal. If you open a new
  terminal, set them again.

### Install host packages

Choose **one** block for your distribution.

**Fedora:**

```bash
sudo dnf install git curl unzip xz python3 gcc make \
  e2fsprogs binutils secilc java-21-openjdk-devel android-tools
```

**Ubuntu 24.04 / Debian with OpenJDK 21 available:**

```bash
sudo apt update
sudo apt install git curl unzip xz-utils python3 python3-venv gcc make \
  e2fsprogs binutils secilc openjdk-21-jdk adb fastboot
```

These provide the C compiler for tests, Java and `keytool` for APK signing,
ext4 image tools, `readelf`, the SELinux policy compiler, and `adb`/`fastboot`.
The package manager installs their shared-library dependencies.
If your distribution does not offer Java 21, use a supported distribution
or install a Java 21+ JDK using its vendor's instructions.

Check:

```bash
java -version
keytool -help
adb version
fastboot --version
command -v debugfs e2fsck resize2fs dumpe2fs readelf secilc cc
```

Java must be 21 or newer. Every tool in the final command should have a path.
If packaged platform-tools are too old, get Google's official
[SDK Platform-Tools for Linux](https://developer.android.com/tools/releases/platform-tools).
Follow Google's [Linux USB/device setup](https://developer.android.com/studio/run/device#setting-up)
if `adb` reports insufficient permissions. Do not solve that by running all
builds as root.

### Get this repository

Skip `git clone` if you already have this folder.

```bash
cd "$HOME"
git clone https://github.com/c6liu/HibreakProPatchingService.git
cd "$HOME/HibreakProPatchingService"
mkdir -p local build
```

Keep downloaded tools in `local/` and generated files in `build/`.
Both are ignored by Git.

## 2. Download the build tools and input images

Use the original publishers below, not repackaged executables from forums.
You do not need a full AOSP build, Gradle, an emulator, CMake, or a separately
installed Android `libhardware` library for this procedure.

| What | Where to get it | Where it goes |
|------|-----------------|---------------|
| Android NDK **27.2.12479018 (r27c), Linux** | Google's [NDK installation instructions](https://developer.android.com/studio/projects/install-ndk#specific-version), or [official older downloads](https://github.com/android/ndk/wiki/Unsupported-Downloads) | Normally `~/Android/Sdk/ndk/27.2.12479018` |
| **apktool 3.0.3** JAR | [Apktool release assets](https://github.com/iBotPeaches/Apktool/releases/tag/v3.0.3) | Save/rename to `local/apktool.jar` |
| **uber-apk-signer 1.3.0** JAR | [Signer release assets](https://github.com/patrickfav/uber-apk-signer/releases/tag/v1.3.0) | Save/rename to `local/uber-apk-signer.jar` |
| Recommended Android 16 GSI | [LineageOS for microG publisher](https://sourceforge.net/projects/lineageos-4-microg/files/GSI/16/) | `~/Downloads/LineageOS-23.2-2026.10.10-microG-gsi.img.xz` |
| Alternative, previously tested GSI | [Doze-off EvoX releases](https://github.com/Doze-off/EvoX_treble/releases) | `~/Downloads/EvoX-11.11-GSI_treble_arm64-ab-MICROG-20260920.img` |
| Original E-Ink APK source image | [vbbot's 20250507 release](https://github.com/vbbot/HibreakProPatchingService/releases/tag/20250507), asset `evolution_arm64_bgN-10.5-unofficial-20250507.img.xz` | Download to `~/Downloads/`; extract only the APK below |

On GitHub, expand **Assets** and download the `.jar`, not the source-code
archive. To install the tested NDK through Android Studio, install
[Android Studio from Google](https://developer.android.com/studio/install#linux),
open **SDK Manager > SDK Tools**, enable **Show Package Details**, and select
**NDK (Side by side) 27.2.12479018**. Note the SDK location shown there.
This older NDK is the tested version, not a claim that it is still supported
upstream.

Set the NDK location; change it if you chose a different install directory:

```bash
export ANDROID_NDK_HOME="$HOME/Android/Sdk/ndk/27.2.12479018"
ls "$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android30-clang"
```

### Extract and check the GSI

Use **arm64 A/B, raw ext4** images. The patcher does not support EROFS.
Extract `.xz` archives first; do not pass an archive to the patcher.
For LineageOS:

```bash
xz -dk "$HOME/Downloads/LineageOS-23.2-2026.10.10-microG-gsi.img.xz"
export BASE="$HOME/Downloads/LineageOS-23.2-2026.10.10-microG-gsi.img"
sha256sum "$BASE"
```

Expected raw-image SHA-256:

```text
5347a165c2911f84915fbdd0e14065a7fbc1cbdcd0b6e571387252e6b36769b8
```

**Alternatively, for the tested EvoX base**, extract its archive if necessary
and set `BASE` to that image instead:

```bash
export BASE="$HOME/Downloads/EvoX-11.11-GSI_treble_arm64-ab-MICROG-20260920.img"
sha256sum "$BASE"
```

Expected raw-image SHA-256:

```text
d25aeac2b42012e76e8f4fd95d69f9e28ceeac64289d85f194d72ef0249374bf
```

Use only one `BASE`. Do not continue if its checksum differs from the
corresponding value. These pinned instructions do not automatically apply
to newer releases. EvoX's known Kindle download issue is documented in
[Findings](docs/FINDINGS.md#third-party-app-issues).

### Extract the original E-Ink APK

**Do not flash the old vbbot image.** It is only an APK source.

```bash
xz -dk "$HOME/Downloads/evolution_arm64_bgN-10.5-unofficial-20250507.img.xz"
debugfs -R "dump system/priv-app/A9AccessibilityService/A9AccessibilityService.apk local/A9AccessibilityService.apk" \
  "$HOME/Downloads/evolution_arm64_bgN-10.5-unofficial-20250507.img"
sha256sum local/A9AccessibilityService.apk
```

Expected APK SHA-256:

```text
7e45b54372dd21070cbfbb33f0c0b19bb0aea57382d2e6bab92896db747d6ed7
```

The builder rejects other APKs. If a file is already extracted, skip the
extraction command rather than overwriting it.

## 3. Back up stock firmware and prepare the optional IR inputs

**Before unlocking**, copy personal files off the phone. A partition backup
with `--skip=userdata` does **not** back up your photos, apps or settings.

Use the original [mtkclient project](https://github.com/bkerler/mtkclient):

1. Follow its [Linux installation instructions](https://github.com/bkerler/mtkclient/blob/main/README-INSTALL.md),
   including Python dependencies, `libusb`, and USB/udev rules for your distro.
   Use its virtual-environment instructions; do not install Python packages
   into the system interpreter with `sudo pip`.
2. Read its [usage instructions](https://github.com/bkerler/mtkclient/blob/main/README-USAGE.md)
   and the device-specific [HiBreak Pro backup/unlock notes](https://vbh.ai/unlocking-the-bootloader-and-rooting-the-hibreak-pro/).
3. From the **mtkclient folder**, using its configured Python environment,
   run this read-only backup command, then connect the powered-off phone as
   those instructions describe:

```bash
python mtk.py rl hibreak-backup --skip=userdata
```

Keep the whole backup and copy it to another drive. Check that the command
completed without errors and that you have nonempty `vbmeta_a.bin`,
`vbmeta_system_a.bin`, `vbmeta_vendor_a.bin`, and the stock partition images.
If files are missing, stop; do not unlock or flash using someone else's backup.
The backup may be inside the mtkclient folder, not this project's folder.

### IR only: obtain the matching stock vendor image

Skip the rest of section 3 if you do not want IR. The IR overlay needs a
**raw ext4 vendor image from your stock 3.1.6 backup** to validate policy.
It reads this file; it does not flash or modify vendor.

If vendor is stored inside the backup's `super.bin`, extract `vendor_a`
from it using a verified `lpunpack` tool. AOSP documents the
[dynamic-partition tools](https://android.googlesource.com/platform/system/extras/+/refs/tags/android-12.0.0_r1/partition_tools/).
Use a package from your distribution's signed repositories, if available,
or a tool built from a reviewed, pinned AOSP revision. Do not download
an arbitrary executable or clone a third-party default branch and immediately
run its script. A local extraction program can access your other files,
including signing keys; "runs locally" does not make untrusted code safe.

This guide does not supply a verified standalone extractor. If your backup
contains only `super.bin` and you cannot establish the tool's provenance,
stop here and get help preparing the vendor image, or continue with a
display-only build. Do not upload your firmware backup to an online extractor.
Keep the original backup unchanged and extract a working copy without root.

If your backup already contains a separate raw vendor image, use that
instead. Do not rename a complete `super.bin` to `vendor_a.img`.
Set `VENDOR` to the actual verified raw vendor file (replace this example
path), then check it:

```bash
export VENDOR="/path/to/extracted-vendor/vendor_a.img"
ls -lh "$VENDOR"
debugfs -R "cat /etc/selinux/plat_sepolicy_vers.txt" "$VENDOR"
```

The last command must read a policy version, not an invalid-filesystem
error. Extraction alone does not prove the backup matches your firmware.
If extraction fails or the partition is absent, stop and inspect your
backup/tool instructions rather than substituting another firmware's vendor.

### IR only: download the public HAL headers

The NDK provides Android system libraries but omits the legacy Consumer IR
HAL headers. Get the Android 12 public headers from Google's AOSP source;
do not download a proprietary replacement HAL or invent ABI declarations.
These two shallow source checkouts and three symlinks provide the includes:

```bash
git clone --depth 1 --branch android-12.0.0_r1 \
  https://android.googlesource.com/platform/hardware/libhardware \
  local/aosp-libhardware
git clone --depth 1 --branch android-12.0.0_r1 \
  https://android.googlesource.com/platform/system/core \
  local/aosp-system-core
mkdir -p local/ir-hal-headers
ln -s ../aosp-libhardware/include/hardware local/ir-hal-headers/hardware
ln -s ../aosp-system-core/libcutils/include/cutils local/ir-hal-headers/cutils
ln -s ../aosp-system-core/libsystem/include/system local/ir-hal-headers/system
export AOSP_HEADERS="$PWD/local/ir-hal-headers"
```

If you already prepared these headers, skip cloning/linking and set only
`AOSP_HEADERS`. Do not overwrite an existing working header directory.
The headers include the graphics/native-handle declarations transitively;
the full include directories above preserve those dependencies.

## 4. Unlock the bootloader (first installation only)

**This erases the phone.** Skip this section if it is already unlocked.
On the phone, enable Developer options (tap **Build number** seven times),
then enable **OEM unlocking** and **USB debugging**.
Connect USB, unlock the screen, and accept the computer authorization prompt.

```bash
adb devices
```

The phone should be listed as `device`. If it says `unauthorized`, accept the
prompt. If it is absent, fix the cable/USB permissions first. Then:

```bash
adb reboot bootloader
fastboot devices
fastboot flashing unlock
```

Confirm the unlock on the phone. After it restarts, remember the Power-button
workaround. Complete enough stock setup to re-enable USB debugging and
authorize the PC. Google's
[ADB documentation](https://developer.android.com/tools/adb) and the
[HiBreak-specific unlock guide](https://vbh.ai/unlocking-the-bootloader-and-rooting-the-hibreak-pro/)
explain these modes in more detail.

## 5. Set up APK signing

Use a stable private signing key for a distributable build. Keep the same
key for future updates. A key is **not** your ADB key and is not included in
the image. See Google's [app-signing guide](https://developer.android.com/studio/publish/app-signing).

**Already have a release key?** Skip creation and set the variables below
to its path, alias and certificate fingerprint.

To create one **once**:

The directory, filename and alias below are generic examples. Choose your
own values; do not publish your actual signing configuration.

```bash
mkdir -p "$HOME/release-signing"
chmod 700 "$HOME/release-signing"
keytool -genkeypair -storetype JKS \
  -keystore "$HOME/release-signing/example-release.jks" \
  -alias example-release -keyalg RSA -keysize 4096 -validity 10000
```

Answer the prompts. Keep passwords private; do not put them in command
lines, screenshots, Git or chat. Back up the keystore securely.
Do not regenerate it for every build.

```bash
export APK_RELEASE_KEYSTORE="$HOME/release-signing/example-release.jks"
export APK_RELEASE_KEY_ALIAS="example-release"
keytool -list -v -keystore "$APK_RELEASE_KEYSTORE" -alias "$APK_RELEASE_KEY_ALIAS"
```

Copy the **SHA256** certificate fingerprint from that output and replace
the placeholder here. Colons are accepted:

```bash
export APK_RELEASE_CERT_SHA256="PASTE_YOUR_CERTIFICATE_SHA256_HERE"
```

The builder checks that fingerprint and prompts for signing passwords.
Without all three variables, it either refuses an incomplete configuration
or uses debug signing when none are set. Debug signing is not for release.

**Updating a debug-signed or differently signed image:** do not assume the
new E-Ink APK will preserve its old data. Android signature mismatches may
require app-data cleanup or a clean install. Back up first.

## 6. Build your release candidate

Return to the project folder. Use the same terminal in which you set the
variables. If you opened another one, set `ANDROID_NDK_HOME`, `BASE`, the
three signing variables and, for IR, `VENDOR` and `AOSP_HEADERS` again.

```bash
cd "$HOME/HibreakProPatchingService"
tools/build-apk.sh local/A9AccessibilityService.apk build/HiBreakEink-release.apk
tools/build-daemon.sh build/a9_eink_server-release
```

Stop on an error. On success, build the display/AOD release base:

```bash
tools/patch-gsi.sh "$BASE" build/HiBreakPro-release-base.img \
  build/HiBreakEink-release.apk build/a9_eink_server-release --release
```

Do not add an ADB key or `--root`. These scripts refuse existing output
files: when rebuilding, choose new output names consistently rather than
deleting your only known-working image.

### Add IR support (optional)

Skip this subsection for display-only builds.

```bash
tools/build-ir-hal.sh build/consumerir.hxd-release.so
python3 -m unittest tools.tests.test_hxd_nec tools.tests.test_hxd_learn \
  tools.tests.test_ir_overlay tools.tests.test_ir_remote
```

Check the tests pass without missing-dependency skips. First run the IR
preflight; **this command does not create an image**:

```bash
python3 tools/add-ir-capture-to-gsi.py \
  build/HiBreakPro-release-base.img build/HiBreakPro-release-ir.img \
  --hal-module build/consumerir.hxd-release.so \
  --vendor-image "$VENDOR" --secilc secilc --check-only
```

If it succeeds and you are ready to package, run it without `--check-only`:

```bash
python3 tools/add-ir-capture-to-gsi.py \
  build/HiBreakPro-release-base.img build/HiBreakPro-release-ir.img \
  --hal-module build/consumerir.hxd-release.so \
  --vendor-image "$VENDOR" --secilc secilc
```

Start from the clean release base, not an old IR test image. This installs
the NEC adapter, its init action and scoped SELinux policy. It does **not**
include either test app, capture/camera services or private IR request hooks.
Do not add `--diagnostics-binary`, `--remote-apk`, or `--api-test-apk` to a
normal release build. Development opt-ins are in [Building](docs/BUILDING.md#optional-ir-support-for-a-release-candidate).

The policy preflight may report existing GSI/vendor neverallow conflicts.
It rejects new conflicts introduced by the overlay; existing conflicts are
not proof that the upstream ROM is production-ready. SELinux remains enforcing.

### Select and check the final image

Choose **one**:

```bash
# With IR:
export IMAGE="$PWD/build/HiBreakPro-release-ir.img"
```

```bash
# Without IR:
export IMAGE="$PWD/build/HiBreakPro-release-base.img"
```

```bash
e2fsck -fn "$IMAGE"
sha256sum "$IMAGE"
```

Stop if the filesystem check fails. Save the checksum alongside any image
you distribute. `--release` makes a **release candidate**: it does not sign
the whole ROM for verified boot/OTA, change every upstream debug setting, or
grant redistribution rights. Test the final image before distributing it.
See [release caveats](docs/BUILDING.md#3-patch-the-gsi-offline).

**Building never flashes a phone.** Stop here if you only wanted an image.

## 7. First install on slot A

**Destructive: this wipes shared userdata and removes slot A's stock
`product`/`system_ext` partitions.** It is for a first migration from stock,
not an ordinary update. Leave stock slot B unchanged as a possible fallback,
but remember it shares the erased data partition.

### 7.1 Prepare slot A's verification metadata

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

### 7.2 Check fastbootd, preview, then flash

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
or partial partition deletion**; see troubleshooting.

**Press Power right after the Bigme logo flashes.**

## 8. First-boot setup

1. Complete Android setup.
2. Open **E-Ink Settings**, enable its accessibility service and allow
   **Display over other apps**.
3. Double-press the E-Ink button to open the refresh menu:
   **HD, Regal, Fast, Extreme, Hyper**.
4. Optional settings:
   - Choose separate single/double/long-press actions for the top and bottom
     buttons. To launch an app, choose **Launch App**, then its target in
     **App to launch** directly below. Screen-off launches wake the display
     but do not bypass the lock screen.
   - Choose per-app refresh modes or enable **Disable Per-App Refresh Mode**
     for one shared mode.
   - Set AOD inversion. Video refresh is experimental and opt-in per app.

USB debugging is not forced on by these release commands. Enable it in
Developer options when needed and authorize the PC on-screen. Updates
without a wipe preserve saved debugging settings and authorizations.

### Using IR

If you included IR, use an ordinary Consumer IR app such as IR Blaster.
No root, private test app or E-Ink accessibility setting is needed for IR.
Current support is **one NEC/NECext frame** at nominal **38000 or 38222 Hz**.
Both values select the same built-in controller carrier, not independently
measured frequencies. Other protocols, standalone repeat frames and bundled
repeat sequences are rejected. Learning is not a supported user feature.
An API success does not confirm that the appliance received the command.

Test apps previously installed in userdata may remain after an image update.
Remove them separately in Android app settings if no longer needed.

## Updating the same GSI

Back up personal files. Build a new image using the **same signing key**.
Set `IMAGE` to that new file. Do not reuse the first-install deletion/wipe
flags or reflash vbmeta:

```bash
adb reboot fastboot
fastboot getvar is-userspace
fastboot getvar current-slot
tools/flash-system.sh "$IMAGE" a
```

Expect `yes` and slot `a`, then execute:

```bash
tools/flash-system.sh "$IMAGE" a --flash
```

This preserves userdata; it does not guarantee every upstream GSI update is
compatible. **Press Power after reboot.** The E-Ink APK is a persistent
system app, so update it through a new image, not `adb install`.

## Switching GSIs (for example, EvoX to LineageOS)

**Plan to erase all data.** Back up personal files and build the desired GSI.
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
recovery. **Press Power after reboot**, then repeat first-boot setup.

## Troubleshooting

| Problem | What to do |
|---------|------------|
| Terminal closes after a failed command | Do not use `set -euo pipefail` interactively. Open a terminal, return to the project folder and set your variables again. |
| `Missing dependency` / `command not found` | Recheck sections 1-3. NDK tools come from Google; `secilc` and `readelf` come from distro packages. |
| Missing `hardware/consumerir.h`, `cutils/...` or `system/graphics...` | Check `AOSP_HEADERS` and all three include directories from section 3. |
| `Refusing to overwrite` / output already exists | Choose new output names consistently. Do not delete the original GSI or your only working image. |
| Signing fingerprint mismatch | Inspect `keytool -list -v` for the selected alias and set its SHA256 fingerprint. Do not bypass verification. |
| `adb` says `unauthorized` | Unlock the phone and accept its authorization dialog. |
| USB permission denied | Follow Google's Linux device setup and mtkclient's udev instructions; reconnect after applying rules. |
| Phone turns off after restart | Press Power right after the Bigme logo flashes, every time. |
| `reap_urb` / `Protocol error` during flash | System may be incomplete. Stay in fastbootd, check `fastboot devices`, reconnect with a direct port/good cable and retry the complete system flash. Do not reboot or wipe first. |
| `Invalid sparse file format at header magic` | Alone, this can be harmless while fastboot converts a raw image. The entire flash must still finish successfully. |
| Recovery says "Can't load Android system" on first install | After confirming the system flash succeeded, use **Factory data reset**; this erases data. |
| IR app reports no emitter | Confirm you flashed the IR image, not just the display base. A test APK alone cannot add the HAL. |
| IR emitter exists but the appliance does not respond | Check NEC/NECext, carrier alias and repeat settings. Changing frequency cannot turn an unsupported protocol into NEC. |

For display/app problems, enable USB debugging and collect read-only logs:

```bash
tools/collect-diagnostics.sh build/diagnostics
```

See [Findings](docs/FINDINGS.md) and [detailed building/verification](docs/BUILDING.md)
before making additional device changes.

**Return to stock slot B:** only if you left its stock partitions intact,
enter bootloader mode and run `fastboot --set-active=b`, then
`fastboot reboot`. Shared userdata may be incompatible and need a factory
reset. This is not a substitute for a full backup; use the mtkclient recovery
instructions for a complete restore.

## Reference guides

- Google: [ADB](https://developer.android.com/tools/adb),
  [Linux device setup](https://developer.android.com/studio/run/device#setting-up),
  [NDK installation](https://developer.android.com/studio/projects/install-ndk),
  [APK signing](https://developer.android.com/studio/publish/app-signing).
- Device-specific community author:
  [HiBreak Pro GSI notes](https://vbh.ai/hibreak-pro-gsi-release/),
  [backup/unlock guide](https://vbh.ai/unlocking-the-bootloader-and-rooting-the-hibreak-pro/),
  [Android 15 installation background](https://vbh.ai/hibreak-pro-guide-4-flashing-the-android-15-gsi/).
  Those older articles explain the device; use this repository's commands
  for the current Android 16 workflow.
- [mtkclient's own documentation](https://github.com/bkerler/mtkclient).
- [IR investigation and exact limitations](docs/HIBREAK_PRO_IR.md).
