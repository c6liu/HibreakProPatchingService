# Tests

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
