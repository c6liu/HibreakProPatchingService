# GSI patcher behavior

Options and image changes made by [patch-gsi.sh](../../tools/image/patch-gsi.sh).
The shell entry point delegates to [patch-gsi.py](../../tools/image/patch-gsi.py),
which uses the shared image helpers under `tools/hibreak/`.
For the normal release commands, use
[Build a release image](../build/build-image.md).

## Personal debug builds with an ADB key

For personal debugging builds, you can embed **your own ADB public key**:

```bash
adb start-server
# If the key does not exist, generate it using: adb keygen "$HOME/.android/adbkey"
tools/image/patch-gsi.sh /path/to/EvoX-11.11-GSI_treble_arm64-ab-MICROG-20260920.img \
  build/HiBreakPro.img build/HiBreakEink.apk build/a9_eink_server \
  "$HOME/.android/adbkey.pub"
```

Never supply `adbkey` (the private key), only `adbkey.pub`. The key is validated
and installed as `/adb_keys`, labelled `adb_keys_file`. That host is authorized
for the image, so **do not distribute a personal-key image to other users**.
Embedding a key does not itself enable USB debugging. Enable it in Developer
options on the phone when needed; the patched image's USB default is MTP,
not ADB. ADB authentication remains
enabled. Omitting the last argument preserves the
GSI's existing key setup; authorize the computer on-screen when prompted.

## Release candidates

For a public-release candidate, use `--release` and do not pass an ADB key:

```bash
tools/image/patch-gsi.sh /path/to/EvoX-11.11-GSI_treble_arm64-ab-MICROG-20260920.img \
  build/HiBreakPro-release.img build/HiBreakEink.apk build/a9_eink_server \
  --release
```

Build the APK with the release signing variables first. The historical
LineageOS input keeps `ro.debuggable=1` from the upstream image;
`--release` does not change it.

## Image defaults and release mode

The patcher does not change the external-storage backend. Earlier builds set
`external_storage.sdcardfs.enabled=false`, but the Android 16 `vold` in the
tested GSIs forces `sdcardfs` for `Android/data` and `Android/obb` on this
kernel anyway, and the property only made `vold` prepare those directories as
if FUSE were in use. Kindle downloads still fail on these GSIs; see
[Findings](../research/display/third-party-apps.md).

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

Root is off by default: all builds remove the base image's `/system/xbin/su`.
The historical LineageOS input had a setuid root binary for the ADB shell.
Pass `--root` to keep a base image's `su`, for example for development.
TrebleDroid's own property handlers run from init and keep working without it.

Release mode additionally removes the project's `debug.hibreak.*` diagnostic
property hooks. It does not inject a host ADB key. The base image's ADB-key path is
otherwise preserved; Android's upstream `ro.secure` and `ro.debuggable` settings
remain unchanged. The historical LineageOS input has `ro.secure=1` and
`ro.debuggable=1`; `--release` does not convert it from userdebug to a
production user build or guarantee ADB is off on a fresh install.
Display-related SurfaceFlinger properties and the internal
`debug.tracing.screen_state` AOD triggers are retained because the device
display/AOD setup uses them; release mode does not strip those required
behavioral settings.

`--release` only strips the project's diagnostic hooks; it
does **not** sign the whole ROM image, establish verified boot/OTA trust, or
resolve upstream ROM redistribution requirements.

The patcher:

1. Copies the input, expands ext4, and unshares ext4 `shared_blocks`.
2. Sets MTP-only USB and ADB
   authorization defaults, removes `/system/xbin/su` unless `--root` is
   passed, and adds the display and AOD services (they run as root under
   phhsu_daemon), preserving saved USB debugging state.
3. Installs the APK, daemon and privileged-permission allowlist.
4. Sets and checks file modes, ownership, SELinux labels and round-trip bytes.
5. Minimizes the filesystem, checks it with `e2fsck`, and prints SHA-256.
6. Verifies that no project boot hook overrides the saved ADB state; in
   `--release` mode, also omits the project's diagnostic-trigger hooks.

It can replace this workflow's files in an already-patched image, but a clean
original GSI is preferred. It refuses a conflicting AOSP daemon init file;
separate stage-one/display and stage-two/e-ink patch runs are no longer needed.
The old session-only five-mode/AOD image-update scripts are superseded.
