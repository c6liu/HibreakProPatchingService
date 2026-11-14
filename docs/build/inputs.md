# Download build tools and input images

Use the original publishers below, not repackaged executables from forums.
The Eink Settings APK is built only from checked-in Kotlin/resources. A full AOSP build,
emulator, CMake, or original APK extraction is not needed.

| Release-builder selection | APK prerequisites |
|---------------------------|-------------------|
| No APK argument, or `--source-apk` (default) | Gradle, Android SDK, JDK, and uber-apk-signer; see [source prerequisites](#source-apk-prerequisites) |
| `--built-apk /path/to/signed.apk` | Already signed source-built APK, Java, and uber-apk-signer for verification |

Every image build also needs the GSI and NDK to compile the daemon. The
default tested-device build includes IR and XRZ, so it also needs the
[HAL headers and matching vendor](ir-inputs.md), `secilc`, and SETools in
the selected Python. Compatibility builds can disable those overlays.

| What | Where to get it | Where it goes |
|------|-----------------|---------------|
| Android NDK **27.2.12479018 (r27c), Linux** | Google's [NDK installation instructions](https://developer.android.com/studio/projects/install-ndk#specific-version), or [official older downloads](https://github.com/android/ndk/wiki/Unsupported-Downloads) | Normally `~/Android/Sdk/ndk/27.2.12479018` |
| **uber-apk-signer 1.3.0** JAR | [Signer release assets](https://github.com/patrickfav/uber-apk-signer/releases/tag/v1.3.0) | Save/rename to `local/uber-apk-signer.jar` |
| Recommended Android 16 GSI | [Doze-off EvoX releases](https://github.com/Doze-off/EvoX_treble/releases) | `~/Downloads/EvoX-11.11-GSI_treble_arm64-ab-MICROG-20260920.img` |
| **apktool 3.0.3** JAR (optional inspection tests only) | [Apktool release assets](https://github.com/iBotPeaches/Apktool/releases/tag/v3.0.3) | Save/rename to `local/apktool.jar` |

On GitHub, expand **Assets** and download the `.jar`, not the source archive.
To install the tested NDK through Android Studio, install
[Android Studio from Google](https://developer.android.com/studio/install#linux),
open **SDK Manager > SDK Tools**, enable **Show Package Details**, and select
**NDK (Side by side) 27.2.12479018**. Note the SDK location shown there.
This older NDK is the tested version, not a claim of continued upstream support.

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

Expected raw-image SHA-256:

```text
d25aeac2b42012e76e8f4fd95d69f9e28ceeac64289d85f194d72ef0249374bf
```

These pinned instructions do not automatically apply to newer releases.
EvoX's known Kindle download issue is documented in
[Findings](../research/display/third-party-apps.md).
Do not continue if the checksum differs. Use only one `BASE`.

## Source-APK prerequisites

Install Gradle 9.8.2, a JDK, and an Android SDK with platform 35 and build tools
36.0.0. The Android Gradle Plugin is pinned to 9.5.0. Source builds have been
tested on Linux with JDK 27; Robolectric tests need a compatible test JVM
(tested with Java 25, not Java 27).

```bash
export ANDROID_HOME="$HOME/Android/Sdk"
android --sdk "$ANDROID_HOME" sdk install platforms/android-35
android --sdk "$ANDROID_HOME" sdk install build-tools/36.0.0
gradle --version
```

Accept SDK licenses when prompted. Gradle resolves plugins and AndroidX/Material
dependencies from Google Maven and Maven Central, so the first build requires
network access. It may also install missing SDK components. See
[Build a release image](build-image.md) for commands, signed source-APK reuse,
and device-validation requirements.
