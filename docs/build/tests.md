# Tests

For changes to the unified release entry point or APK build flow:

```bash
python3 -m unittest tools.tests.test_build_release tools.tests.test_source_apk -v
```

The orchestration tests mock expensive build commands. They cover default
source builds, explicit source/upstream selection, unchanged signed-APK reuse,
certificate verification failures, IR-to-XRZ ordering, environment defaults,
and forwarding NDK/header/compiler paths. They do not compile a real policy
or prove device compatibility. APK artifact inspection is opt-in as described
below; without `HIBREAK_SOURCE_APK`, that test class is skipped.

For changes to the IR or XRZ image overlays, the focused host suite is:

```bash
python3 -m unittest tools.tests.test_ir_overlay tools.tests.test_xrz_compat -v
```

XRZ tests check exact property selection, permission-preservation guards,
conditional-rule rejection, image round-trips, source preservation, and
overwrite/failure cleanup. Real merged-policy validation additionally needs
the matching vendor image, `secilc`, and SETools; use the
[XRZ preflight](xrz-overlay.md). Neither host tests nor preflight establish
on-device property writes or a graphics-crash fix.

For the full host suite:

```bash
python3 -m unittest discover -s tools/tests -v
for script in tools/*.sh tools/display/*.sh; do bash -n "$script"; done
shellcheck --shell=sh tools/display/*.sh
shellcheck tools/lib/*.sh
```

Tests use disposable ext4 images in `build/`, not a phone. They cover payloads,
metadata, source preservation, paths with spaces, ADB key handling, overwrite
and format rejection, and flashing safeguards. Settings resource tests also
check category order and dependencies. When the tested base APK and apktool
are present in `local/` (or `APKTOOL_JAR` is set), APK tests decode, patch and
assemble the settings UI; otherwise those APK tests are skipped.

To inspect an already built experimental source APK, run:

```bash
ANDROID_HOME="$HOME/Android/Sdk" \
HIBREAK_SOURCE_APK="$PWD/build/HiBreakEink-source-experimental.apk" \
  python3 -m unittest tools.tests.test_source_apk -v
```

This requires apktool and Android build tools 36.0.0. It checks the compiled
manifest, boot receiver's hidden-API reference, exclusion of the compile-only
stub, settings resources, version, and signature. It does not access a device.
Optionally set `HIBREAK_PATCHED_APK` to the supported patched APK to compare
their permissions, component contracts, preferences, refresh/action choices,
shared popup controls, and signing certificates. The certificate check expects
both APKs to use the same key. The patched APK retains hidden legacy AOD view
IDs which are intentionally absent from the source layout.
Before considering the source route for release, separately test on the target
device: boot-time service activation, settings and preference migration,
per-app modes, both side keys (including screen-off gestures and app launch),
quick settings, display controls, and AOD/video-refresh behavior. Check upgrades
with the intended signing certificate as well. The source APK has not yet
passed those parity checks.

To additionally check all four DPAD action dispatches, popup inflation and
video-switch setup, and screen-off/on receiver execution on a connected Android
device, run `HIBREAK_ADB_TESTS=1 python3 -m unittest tools.tests.test_apk_settings`.
These existing instrumentation tests exercise the **patched** APK, not the
source-built APK.
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
