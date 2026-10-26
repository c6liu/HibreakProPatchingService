# Build and patch a HiBreak Pro GSI

## Scope and prerequisites

This procedure is for the black-and-white HiBreak Pro, MT6877, stock vendor
3.1.6 / `Bigme_HiBreak_V1.0_20260306`, kernel 4.19.191. The tested input is
Doze-off's `EvoX-11.11-GSI_treble_arm64-ab-MICROG-20260920.img`.
The original raw image's SHA-256 is:

```text
d25aeac2b42012e76e8f4fd95d69f9e28ceeac64289d85f194d72ef0249374bf
```

Use **arm64 A/B, ext4**. Extract compressed images first. Android sparse
images need `simg2img`; EROFS is not supported by this patcher or the tested
stock kernel. The script requires a TrebleDroid `vndk.rc` using the existing
`phhsu_daemon` domain. It does not add a new SELinux policy or disable SELinux.
Check other firmware/GSIs independently; do not assume compatibility.

Host requirements:

- Linux x86-64, Bash, Python 3, Java (Java 21 or newer recommended), coreutils.
- e2fsprogs: `debugfs`, `e2fsck`, `resize2fs`, `dumpe2fs`; `mke2fs` for tests.
- Android platform-tools: `adb`, `fastboot`.
- Android NDK, tested with **27.2.12479018** (API 30 arm64 compiler).
- [apktool 3.0.3](https://github.com/iBotPeaches/Apktool/releases/tag/v3.0.3).
- [uber-apk-signer 1.3.0](https://github.com/patrickfav/uber-apk-signer/releases/tag/v1.3.0).
- Enough disk space for the original GSI, a second full image, and temporary
  files (allow at least 10 GiB free). No root/mount is needed on the host.

Install missing dependencies using your distribution/Android SDK tools. On
Fedora the host packages include `e2fsprogs java-21-openjdk-headless python3
android-tools`; on Debian/Ubuntu, `e2fsprogs openjdk-21-jre-headless python3
adb fastboot`. NDK installation/license acceptance is separate.

Run the commands below from the repository root. All paths are examples;
there is no dependency on a previous user's home or chat-session directory.

```bash
mkdir -p local build
# Put apktool.jar and uber-apk-signer.jar in local/.
# Alternatively set APKTOOL_JAR and APK_SIGNER_JAR to their installed paths.
export ANDROID_NDK_HOME="$HOME/Android/Sdk/ndk/27.2.12479018"
```

## 1. Obtain the tested base APK

Download and extract
[`evolution_arm64_bgN-10.5-unofficial-20250507.img.xz`](https://github.com/vbbot/HibreakProPatchingService/releases/tag/20250507).
**Do not flash that image for this build procedure.** Extract only its app:

```bash
debugfs -R "dump system/priv-app/A9AccessibilityService/A9AccessibilityService.apk local/A9AccessibilityService.apk" \
  /path/to/evolution_arm64_bgN-10.5-unofficial-20250507.img
sha256sum local/A9AccessibilityService.apk
```

Expected APK SHA-256:

```text
7e45b54372dd21070cbfbb33f0c0b19bb0aea57382d2e6bab92896db747d6ed7
```

The APK patcher deliberately rejects other binaries: it edits specific
R8-generated smali and resource layouts, not arbitrary A9 APK versions.
Patching a newer APK needs porting and validating those edits. Stock Bigme
xSettings is **not** a drop-in replacement; it depends on the stock framework.

The checked-in Kotlin/resources are the source implementation. Offline APK
rebuilding uses the tested upstream APK plus [patch-apk.py](../tools/patch-apk.py)
because this repository is an AOSP module, not a standalone Gradle project.
Do not expect arbitrary Kotlin edits to be picked up by the APK patcher.

## 2. Build the app and daemon

```bash
tools/build-apk.sh local/A9AccessibilityService.apk build/HiBreakEink.apk
tools/build-daemon.sh build/a9_eink_server
```

The APK gains five modes, the in-layout toolbar, the AOD inversion switch, and
per-app refresh selectors on a separate page for installed launcher apps, with
a confirmed reset-all action. Button settings appear
top-first. Unsupported legacy static-lockscreen controls are removed/hidden;
the legacy max-brightness override is removed.
It has `sharedUserId` removed so it can run without the GSI's platform signing
key. The AOSP module keeps its platform-signed integration configuration.

The offline builder uses uber-apk-signer's debug signing configuration, matching
the development images made during this investigation. This is for personal
testing, **not a production signing strategy**. Keep a stable, privately managed
release key for distributed releases, adapt the signing step accordingly, and
never commit private keys. Changing the certificate between images can reset
the app's settings. The signing tool verifies its output.

All builders refuse to overwrite existing outputs. Choose new filenames when
rebuilding. A failed image build can leave an incomplete output; do not flash it.

## 3. Patch the GSI (offline)

For first-boot debugging with a black screen, embed **your own ADB public key**:

```bash
adb start-server
# If the key does not exist, generate it using: adb keygen "$HOME/.android/adbkey"
tools/patch-gsi.sh /path/to/EvoX-11.11-GSI_treble_arm64-ab-MICROG-20260920.img \
  build/HiBreakPro.img build/HiBreakEink.apk build/a9_eink_server \
  "$HOME/.android/adbkey.pub"
```

Never supply `adbkey` (the private key), only `adbkey.pub`. The key is validated
and installed as `/adb_keys`, labelled `adb_keys_file`. That host is authorized
for the image, so **do not distribute a personal-key image to other users**.
ADB authentication remains enabled. Omitting the last argument preserves the
GSI's existing key setup; authorize the computer on-screen when prompted.

The patcher:

1. Copies the input, expands ext4, and unshares ext4 `shared_blocks`.
2. Adds root/phhsu display, USB-debugging and AOD services.
3. Installs the APK, daemon and privileged-permission allowlist.
4. Sets and checks file modes, ownership, SELinux labels and round-trip bytes.
5. Minimizes the filesystem, checks it with `e2fsck`, and prints SHA-256.

It can replace this workflow's files in an already-patched image, but a clean
original GSI is preferred. It refuses a conflicting AOSP daemon init file.
The old `add-eink-to-gsi.sh` entry point delegates to this unified patcher;
separate stage-one/display and stage-two/e-ink patch runs are no longer needed.
The old session-only five-mode/AOD image-update scripts are superseded.

## 4. Flash only after preparing recovery

**Back up the exact stock firmware and personal data.** Unlocking erases data.
The scripts do not unlock, modify vbmeta, delete partitions, or enlarge super.
Those are device preparation tasks; see [Guide.md](../Guide.md). Use the
**stock vendor**, not the experimental HWC shim. Never flash vendor/boot images
from a different firmware or blindly copy another user's partition commands.

Preview first (no device commands executed):

```bash
tools/flash-system.sh build/HiBreakPro.img a
```

If slot A is the intended, prepared slot:

```bash
adb reboot fastboot
tools/flash-system.sh build/HiBreakPro.img a --flash
```

> **Press Power right after the Bigme logo flashes** on every restart or
> power-up, otherwise the phone can go back to powered-off. Not fixed.

The flashing helper checks that the phone is in fastbootd on slot A, checks the ext4 image, flashes
only `system_a`, and reboots only after a successful flash. It does not switch
slots or wipe data. Do not run `fastboot -w` when updating the patched version
of the same GSI. A first migration from stock/another ROM may need a separately
planned factory reset; the two slots share userdata.

The helper limits sparse transfers to 64 MiB (`fastboot -S 64M`) instead of
using the device's larger default. If flashing fails with `reap_urb` /
`Protocol error`, the USB transfer failed and the system partition may be
incomplete. **Do not reboot or wipe.** Keep the phone in fastbootd, reconnect
USB if necessary, check `fastboot devices`, and retry the complete flash.
Try a direct USB port and a known-good data cable if the failure repeats.
The helper stops without rebooting after a failed flash.

`Invalid sparse file format at header magic` can appear when fastboot reads
the raw ext4 image before converting it into sparse transfers; it alone does
not indicate corruption. The complete flash must finish successfully before
rebooting. Smaller transfers are a retry strategy, not a verified cure for
every USB protocol error.

## 5. Initial setup and verification

Press Power right after the Bigme logo flashes, wait for boot, open E-Ink Settings and enable the accessibility service and
draw-over-other-apps permission. Top/bottom customization buttons have separate
single/double/long-press mappings, including screen-off mappings.

```bash
adb devices
adb shell getprop sys.boot_completed
adb shell getprop debug.sf.enable_gl_backpressure
adb shell getprop debug.sf.enable_hwc_backpressure
adb shell dumpsys SurfaceFlinger | grep 'h/w composer disabled'
adb logcat -d -s hibreak-display a9EinkService
tools/collect-diagnostics.sh build/diagnostics-after-boot
```

Expect boot completion `1`, both backpressure properties `false`, and disabled
HWC. Init oneshot services normally show `stopped` **after successful completion**;
inspect logs, not that state alone. A running daemon also does not prove that
the app can send commands or that the panel responds.

The E-Ink app is a persistent system app: `adb install` fails with
"persistent app, not updateable". Update it by building and flashing a new image.

If the popup still shows the old order after flashing, check the active APK:

```bash
adb shell pm path com.lmqr.ha9_comp_service
```

A `/data/app/` path means an older installed update overrides the system copy.
After confirming the new image contains the corrected app, remove only that
package's update (this may reset app preferences):

```bash
adb shell cmd package uninstall-system-updates com.lmqr.ha9_comp_service
adb shell pm path com.lmqr.ha9_comp_service
```

The path should now be `/system/priv-app/HiBreakEink/HiBreakEink.apk`.
Check accessibility and overlay permissions again. The popup order is
**HD, Regal, Fast, Extreme, Hyper**.

Do not assume a successful package install proves mode speed or AOD appearance.
Test a selected mode, lock/unlock, and inspect the physical panel. See
[Findings](FINDINGS.md) for unsupported controls and the boot power-button issue.

## Tests

```bash
python3 -m unittest discover -s tools/tests -v
for script in tools/*.sh tools/display/*.sh; do bash -n "$script"; done
```

Tests use disposable ext4 images in `build/`, not a phone. They cover payloads,
metadata, source preservation, paths with spaces, ADB key handling, overwrite
and format rejection, and flashing safeguards. Settings resource tests also
check category order and dependencies. When the tested base APK and apktool
are present in `local/` (or `APKTOOL_JAR` is set), APK tests decode, patch and
assemble the settings UI; otherwise those APK tests are skipped.
Device scripts require Android
and the existing phh policy; host tests cannot verify physical display behavior.
