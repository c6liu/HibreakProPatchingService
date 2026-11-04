# Download build tools and input images

Use the original publishers below, not repackaged executables from forums.
You do not need a full AOSP build, Gradle, an emulator, CMake, or a separately
installed Android `libhardware` library for this procedure.

| What | Where to get it | Where it goes |
|------|-----------------|---------------|
| Android NDK **27.2.12479018 (r27c), Linux** | Google's [NDK installation instructions](https://developer.android.com/studio/projects/install-ndk#specific-version), or [official older downloads](https://github.com/android/ndk/wiki/Unsupported-Downloads) | Normally `~/Android/Sdk/ndk/27.2.12479018` |
| **apktool 3.0.3** JAR | [Apktool release assets](https://github.com/iBotPeaches/Apktool/releases/tag/v3.0.3) | Save/rename to `local/apktool.jar` |
| **uber-apk-signer 1.3.0** JAR | [Signer release assets](https://github.com/patrickfav/uber-apk-signer/releases/tag/v1.3.0) | Save/rename to `local/uber-apk-signer.jar` |
| Recommended Android 16 GSI | [Doze-off EvoX releases](https://github.com/Doze-off/EvoX_treble/releases) | `~/Downloads/EvoX-11.11-GSI_treble_arm64-ab-MICROG-20260920.img` |
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

## Extract and check the GSI

Use **arm64 A/B, raw ext4** images. The patcher does not support EROFS.
Extract `.xz` archives first; do not pass an archive to the patcher.
For the recommended EvoX base:

```bash
export BASE="$HOME/Downloads/EvoX-11.11-GSI_treble_arm64-ab-MICROG-20260920.img"
sha256sum "$BASE"
```

Expected raw-image SHA-256 for this pinned EvoX input:

```text
d25aeac2b42012e76e8f4fd95d69f9e28ceeac64289d85f194d72ef0249374bf
```

These pinned instructions do not automatically apply to newer releases.
EvoX's known Kindle download issue is documented in
[Findings](../research/display/third-party-apps.md).

Do not continue if the checksum differs. Use only one `BASE`.

## Extract the original E-Ink APK

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

## Why only this APK is accepted

The APK patcher deliberately rejects other binaries: it edits specific
R8-generated smali and resource layouts, not arbitrary A9 APK versions.
Patching a newer APK needs porting and validating those edits. Stock Bigme
xSettings is **not** a drop-in replacement; it depends on the stock framework.

The checked-in Kotlin/resources are the source implementation. Offline APK
rebuilding uses the tested upstream APK plus [patch-apk.py](../../tools/patch-apk.py)
because this repository is an AOSP module, not a standalone Gradle project.
Do not expect arbitrary Kotlin edits to be picked up by the APK patcher.
