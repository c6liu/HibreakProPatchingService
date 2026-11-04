# Prepare your Linux computer

Use an x86-64 Linux PC, a good USB data cable and a direct USB port.
Allow **at least 40 GiB free**, more for multiple full images/backups.
Keep another copy of the backup on a different drive.

## How to use the commands

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

## Install host packages

To install a prebuilt release you only need Git, `unzip`, `e2fsck`, ADB and
fastboot. Install them using one block. (Building from source needs more;
see [Set up a build computer](../build/host-setup.md).)

**Fedora:**

```bash
sudo dnf install git unzip e2fsprogs android-tools
```

**Ubuntu / Debian:**

```bash
sudo apt update
sudo apt install git unzip e2fsprogs adb fastboot
```

Check `adb version`, `fastboot --version` and `command -v e2fsck unzip git`.
Stock backup also needs the separate mtkclient setup described in
[Back up stock firmware](backup-stock.md).

If packaged platform-tools are too old, get Google's official
[SDK Platform-Tools for Linux](https://developer.android.com/tools/releases/platform-tools).
Follow Google's [Linux USB/device setup](https://developer.android.com/studio/run/device#setting-up)
if `adb` reports insufficient permissions. Do not solve that by running
everything as root.

## Get this repository

Skip `git clone` if you already have this folder.

```bash
cd "$HOME"
git clone https://github.com/c6liu/HibreakProPatchingService.git
cd "$HOME/HibreakProPatchingService"
mkdir -p local build
```

Keep downloaded tools in `local/` and generated files in `build/`.
Both are ignored by Git.
