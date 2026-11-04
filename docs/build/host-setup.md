# Set up a build computer

Read the command rules and USB notes in
[Prepare your Linux computer](../install/prepare-computer.md) and clone the
repository as described there. Building needs these extra packages.

## Install host packages

Choose **one** block for your distribution.

**Fedora:**

```bash
sudo dnf install git curl unzip xz python3 gcc make \
  e2fsprogs binutils secilc shellcheck java-21-openjdk-devel android-tools
```

**Ubuntu 24.04 / Debian with OpenJDK 21 available:**

```bash
sudo apt update
sudo apt install git curl unzip xz-utils python3 python3-venv gcc make \
  e2fsprogs binutils secilc shellcheck openjdk-21-jdk adb fastboot
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
command -v debugfs e2fsck resize2fs dumpe2fs readelf secilc shellcheck cc
```

Java must be 21 or newer. Every tool in the final command should have a path.

## Host requirements summary

- Linux x86-64, Bash, Python 3, Java 21 or newer, coreutils.
- e2fsprogs: `debugfs`, `e2fsck`, `resize2fs`, `dumpe2fs`; `mke2fs` for tests.
- Android platform-tools: `adb`, `fastboot`.
- Android NDK, tested with **27.2.12479018** (API 30 arm64 compiler).
- Default source APK builds: Gradle and Android SDK platform/build tools;
  see [tested source-build prerequisites](inputs.md#experimental-source-apk-prerequisites).
- [apktool 3.0.3](https://github.com/iBotPeaches/Apktool/releases/tag/v3.0.3)
  for upstream APK patching and APK inspection tests, not source builds/reuse.
- [uber-apk-signer 1.3.0](https://github.com/patrickfav/uber-apk-signer/releases/tag/v1.3.0).
- IR/XRZ overlays: `secilc`; XRZ also requires SETools Python bindings in the
  interpreter running the release builder (`python3 -c 'import setools'`).
  If a Homebrew Python lacks the system bindings, use the system Python that
  provides them, such as `/usr/bin/python3`; changing `PATH` alone does not
  add bindings to a different interpreter.
- Enough disk space for the original GSI, a second full image, and temporary
  files (allow at least 10 GiB free; 40 GiB if you also keep backups).
  No root/mount is needed on the host.

NDK installation/license acceptance is separate; see
[Download build tools and input images](inputs.md). Put `apktool.jar` and
`uber-apk-signer.jar` in `local/`, or set `APKTOOL_JAR` and `APK_SIGNER_JAR`
to their installed paths. Run build commands from the repository root. All
paths are examples; there is no dependency on a previous user's home directory.
The [unified release builder](build-image.md) accepts `--ndk` and `--secilc`
or reads `ANDROID_NDK_HOME` and `SECILC`; it does not install these tools.
