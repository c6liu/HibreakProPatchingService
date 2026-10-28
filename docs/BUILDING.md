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

Offline patching is also validated with
`LineageOS-23.2-2026.10.10-microG-gsi.img` (Android 16). Unlike the EvoX input,
it omits `persist.sys.usb.config` from `system/build.prop`; the patcher adds the
MTP default when missing. Its `system_ext/etc/build.prop` also sets
`persist.sys.usb.config=adb` and `ro.adb.secure=0` (ADB without computer
authorization), and it ships a setuid `/system/xbin/su`; the patcher fixes all
three (see below). This verifies image construction, not boot or
on-device display compatibility; those still require device testing.

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

The APK gains five modes, the in-layout toolbar, the AOD inversion switch,
screen-on DPAD button actions, an opt-in video-refresh popup toggle, and per-app
refresh selectors on a separate page
for installed launcher apps, with a confirmed reset-all action. Button
settings appear top-first. Unsupported legacy static-lockscreen controls are
removed/hidden, as are the LCD-only Night Light and Backlight button actions.
The legacy max-brightness override is removed. Build the daemon from the
matching source so it can dispatch the new DPAD commands.
The popup's Auto Refresh, Anti-Shake, and Video Refresh controls are saved
per app, independently of the per-app refresh-mode enable/disable setting.
Auto Refresh and Anti-Shake default on when no global or app-specific value has
been saved; Video Refresh defaults off and the old global video flag is ignored.
The default refresh mode for new apps is Fast. Existing saved global and
per-app choices are preserved. Changing apps applies the new app's controls and updates popup switches
without saving the previous app's values into the new app. Controls remain
disabled until an active app is detected. The per-app page's reset action resets
refresh modes only, not these controls. The camera-preview keep-alive remains
independent of the per-app Video Refresh choice.
It has `sharedUserId` removed so it can run without the GSI's platform signing
key. The AOSP module keeps its platform-signed integration configuration.

By default the offline builder uses uber-apk-signer's debug signing
configuration, for personal testing only. To sign with a stable release key,
set the keystore path, alias, and expected SHA-256 certificate fingerprint.
The signer prompts for passwords; the build script does not accept passwords
as command-line arguments or save them:

```bash
export APK_RELEASE_KEYSTORE="/private/path/to/your-release-key.jks"
export APK_RELEASE_KEY_ALIAS="your-key-alias"
export APK_RELEASE_CERT_SHA256="<your-certificate-sha256-fingerprint-without-colons>"
tools/build-apk.sh local/A9AccessibilityService.apk build/HiBreakEink-signed.apk
unset APK_RELEASE_KEYSTORE APK_RELEASE_KEY_ALIAS APK_RELEASE_CERT_SHA256
```

Replace the placeholders with your own private keystore path, alias, and
certificate fingerprint. The builder requires all three settings together,
asks the signer to verify the expected certificate, and verifies the resulting
APK. Keep the keystore backed up and privately managed; never commit it or its
passwords. Use this same key for every future A9 build. Changing the
certificate may cause Android to reject an update or reset the app's data.
Moving an already-flashed debug-signed system app to the release certificate
requires a fresh migration plan; test on a disposable device before publishing.

All builders refuse to overwrite existing outputs. Choose new filenames when
rebuilding. A failed image build can leave an incomplete output; do not flash it.

## 3. Patch the GSI (offline)

For personal debugging builds, you can embed **your own ADB public key**:

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
Embedding a key does not itself enable USB debugging. Enable it in Developer
options on the phone when needed; the tested EvoX base defaults to ADB off
on fresh installs. ADB authentication remains
enabled. Omitting the last argument preserves the
GSI's existing key setup; authorize the computer on-screen when prompted.

For a public-release candidate, use `--release` and do not pass an ADB key:

```bash
tools/patch-gsi.sh /path/to/EvoX-11.11-GSI_treble_arm64-ab-MICROG-20260920.img \
  build/HiBreakPro-release.img build/HiBreakEink.apk build/a9_eink_server \
  --release
```

For LineageOS, use the same command with
`LineageOS-23.2-2026.10.10-microG-gsi.img` as the input. Build the APK with the
release signing variables first.

All builds set `external_storage.sdcardfs.enabled=false` so Android uses FUSE
instead of the legacy kernel `sdcardfs` layer for emulated external storage.
This is intended to avoid storage compatibility problems on newer Android GSIs
with the stock 4.19 kernel; verify device-specific storage behavior after
flashing.
The property is added to `system/build.prop` and any existing entries in
`system_ext/etc/build.prop` or `product/etc/build.prop` are set to `false` so
they cannot override it.

All builds set the image's default `persist.sys.usb.config` to `mtp`, replacing
an existing entry or adding a missing one in `system/build.prop`. An existing
entry in `system_ext/etc/build.prop` or `product/etc/build.prop`, which would
override it, is also set to `mtp`. Any `ro.adb.secure` entry in those files
is set to `1` so ADB always asks before trusting a computer. Duplicate entries
for these patched properties are rejected. This is done without
forcing USB configuration at boot or changing Android's saved USB debugging
setting. On an update without a data wipe, ADB stays enabled or disabled as
previously selected, and existing computer authorizations remain in userdata.
The tested EvoX base defaults to ADB off on fresh installs; other bases may
have upstream debug policies that enable ADB. Enable or disable USB debugging
in Developer options as needed. A factory reset erases saved settings and
authorizations.
The old helper that forced USB debugging on is removed, including when updating
an already-patched image.

Root is off by default: all builds remove the base image's `/system/xbin/su`
(the LineageOS input's setuid root binary for the ADB shell). Pass `--root` to
keep it, for example for development. TrebleDroid's own property handlers run
from init and keep working without it.

Release mode additionally removes the project's `debug.hibreak.*` diagnostic
property hooks. It does not inject a host ADB key. The base image's ADB-key path is
otherwise preserved; Android's upstream `ro.secure` and `ro.debuggable` settings
remain unchanged. The LineageOS input has `ro.secure=1` and `ro.debuggable=1`;
`--release` does not convert it from userdebug to a production user build or
guarantee ADB is off on a fresh install. Display-related SurfaceFlinger properties
and the internal
`debug.tracing.screen_state` AOD triggers are retained because the device
display/AOD setup uses them; release mode does not strip those required
behavioral settings.

`--release` only strips the project's diagnostic hooks; it
does **not** sign the whole ROM image, establish verified boot/OTA trust, or
resolve upstream ROM redistribution requirements.

The patcher:

1. Copies the input, expands ext4, and unshares ext4 `shared_blocks`.
2. Selects FUSE for emulated external storage, sets MTP-only USB and ADB
   authorization defaults, removes `/system/xbin/su` unless `--root` is
   passed, and adds the display and AOD services (they run as root under
   phhsu_daemon), preserving saved USB debugging state.
3. Installs the APK, daemon and privileged-permission allowlist.
4. Sets and checks file modes, ownership, SELinux labels and round-trip bytes.
5. Minimizes the filesystem, checks it with `e2fsck`, and prints SHA-256.
6. Verifies that no project boot hook overrides the saved ADB state; in
   `--release` mode, also omits the project's diagnostic-trigger hooks.

It can replace this workflow's files in an already-patched image, but a clean
original GSI is preferred. It refuses a conflicting AOSP daemon init file.
The old `add-eink-to-gsi.sh` entry point delegates to this unified patcher;
separate stage-one/display and stage-two/e-ink patch runs are no longer needed.
The old session-only five-mode/AOD image-update scripts are superseded.

## 4. Flash only after preparing recovery

**Back up the exact stock firmware and personal data.** Unlocking erases data.
The scripts do not unlock, modify vbmeta, or enlarge super. The flash helper
leaves logical partitions alone unless explicitly asked to delete
`product_<slot>` and `system_ext_<slot>` with
`--delete-stock-logical-partitions`. See [Guide.md](../Guide.md) for first
migration steps. Use the **stock vendor**, not the experimental HWC shim.
Never flash vendor/boot images from a different firmware or blindly copy
another user's partition commands.

Preview first (no device commands executed):

```bash
tools/flash-system.sh build/HiBreakPro.img a
```

If slot A is the intended, prepared slot:

```bash
adb reboot fastboot
tools/flash-system.sh build/HiBreakPro.img a --flash
```

For a **first migration from official stock firmware** that requires a factory
reset, preview the destructive action first:

```bash
tools/flash-system.sh build/HiBreakPro.img a --wipe-data
```

For the first GSI migration, also pass `--delete-stock-logical-partitions` to
remove the unused `product` and `system_ext` logical partitions for that slot;
this is needed to make room for the GSI. The option is destructive, so inspect
the preview before executing. For example:

```bash
tools/flash-system.sh build/HiBreakPro.img a \
  --delete-stock-logical-partitions --wipe-data
tools/flash-system.sh build/HiBreakPro.img a \
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

## 5. Initial setup and verification

Press Power right after the Bigme logo flashes, wait for boot, open E-Ink Settings and enable the accessibility service and
draw-over-other-apps permission. Top/bottom customization buttons have separate
single/double/long-press mappings, including screen-off mappings.
The "App to launch" row uses the same standard layout as the other settings,
and appears directly below its action only when "Launch App" is selected.
On Android 16, noninteractive keys may be dropped before reaching accessibility.
The root daemon therefore monitors the HiBreak's `mtk-kpd` side-key events without
grabbing the input device and forwards them to a receiver restricted to senders
with `INJECT_EVENTS`. The app accepts the bridge only for gestures starting with
the screen off; normal accessibility input continues to handle screen-on gestures.
Both the updated APK **and daemon** are required, so install this fix with an image
update, not just an APK update. Launching an app wakes the display but does not
bypass a secure lock screen.

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
To additionally check all four DPAD action dispatches, popup inflation and
video-switch setup, and screen-off/on receiver execution on a connected Android
device, run `HIBREAK_ADB_TESTS=1 python3 -m unittest tools.tests.test_apk_settings`.
This opt-in check needs the APK signer too. It installs a disposable,
uniquely named instrumentation package using the patched classes and resources,
with a mock command runner and preferences for popup tests. It does not replace
the A9 app or change its saved settings. It also puts the display to sleep and
verifies that bridged side-key input reaches the gesture mapping, wakes the
display, and launches the temporary app; the display is awakened during cleanup.
The temporary package is uninstalled afterward. It checks popup initialization,
not accessibility-overlay attachment or physical display behavior.
To include the real physical-key path, connect the phone, set
`ANDROID_NDK_HOME`, and run:

```bash
HIBREAK_ADB_TESTS=1 HIBREAK_PHYSICAL_KEY_TESTS=1 \
  python3 -m unittest tools.tests.test_apk_settings -v
```

When prompted in the test output, press the top side key once while the display
is asleep. This compiles and temporarily runs the daemon's input monitor under
ADB shell, targeting only the disposable test package. The monitor is stopped and
removed afterward. This verifies physical input delivery, but an image-level
check is still needed to validate the production daemon's SELinux context.
The runtime check also verifies Additional Controls migration defaults,
per-app isolation and persistence, switch rebinding without unintended writes,
and applying the app's Video Refresh state to the live-refresh manager.
Device scripts require Android
and the existing phh policy; host tests cannot verify physical display behavior.
