# Tests

For source-only APK orchestration, signing, and settings resource changes:

```bash
python3 -m unittest tools.tests.test_build_release tools.tests.test_source_apk tools.tests.test_apk_settings -v
```

Orchestration tests mock expensive build commands. They cover source builds,
rejection of positional upstream APK inputs, signed source-APK reuse,
certificate failures, IR-to-XRZ ordering, environment defaults, and tool paths.
They do not prove device compatibility. Binary APK patching and its smali
instrumentation tests have been removed.

## Source-app runtime tests

```bash
ANDROID_HOME="$HOME/Android/Sdk" gradle --no-daemon :app:testDebugUnitTest :app:assembleRelease
```

Robolectric tests execute the source classes on Android API 35. They verify F9
down/up/repeat consumption without gesture dispatch (including absent and
side-button scan codes), Power/F8/F10 pass-through, Material menu inflation
in light/dark configurations, and selection of all five refresh modes.
Use a Robolectric-compatible Java runtime; Java 25 was tested successfully.
Java 27 can build the app but is not supported by this Robolectric/ASM version.
If Gradle uses Java 27, run tests with a supported JDK or configure Gradle's
`Test` task launcher separately from the compiler.

## Signed source-APK inspection

```bash
tools/build-source-apk.sh build/HiBreakEink-source.apk
ANDROID_HOME="$HOME/Android/Sdk" \
HIBREAK_SOURCE_APK="$PWD/build/HiBreakEink-source.apk" \
  python3 -m unittest tools.tests.test_source_apk -v
```

This opt-in inspection requires apktool and Android build tools 36.0.0.
It checks the manifest, hidden-API boot reference, compile-only stub exclusion,
settings resources, version, and signature. Without `HIBREAK_SOURCE_APK`,
the artifact test class is skipped. It does not access a device.

## Other host tests

```bash
python3 -m unittest tools.tests.test_ir_overlay tools.tests.test_xrz_compat -v
python3 -m unittest discover -s tools/tests -v
for script in tools/*.sh tools/display/*.sh; do bash -n "$script"; done
shellcheck --shell=sh tools/display/*.sh
shellcheck tools/lib/*.sh
```

Host image tests use disposable ext4 images, not a phone. They check payloads,
metadata, source preservation, paths, format/overwrite rejection, policy guards,
and flashing safeguards. Real merged-policy validation needs matching vendor,
`secilc`, and SETools; see [XRZ preflight](xrz-overlay.md).

## Physical-device verification

Before distributing a source-built image, test boot-time service activation,
settings/preference migration, per-app refresh modes, both side keys (screen-on
and screen-off gestures and app launch), quick settings, frontlight controls,
AOD/video refresh, and fingerprint/F9 handling. Verify Material 3 text contrast,
switches, sliders, selected-mode highlighting, dialogs, and back navigation in
both light/dark modes on the physical panel. Check updates with the intended
signing certificate. See [post-install verification](../reference/verification.md).

Neither host tests nor a successful build prove physical display behavior,
production SELinux input delivery, or boot compatibility.
