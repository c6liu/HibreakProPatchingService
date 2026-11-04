# Build a release image

Return to the project folder. Use the same terminal in which you set the
variables. If you opened another one, set `ANDROID_NDK_HOME` and `BASE`
([inputs](inputs.md)), the three [signing variables](signing.md) and, for IR,
`VENDOR` and `AOSP_HEADERS` ([IR inputs](ir-inputs.md)) again.

For a single-command release build, use the orchestrator. It creates a new
timestamped directory under `build/`, retains its intermediates, writes a
`manifest.json` with input/output checksums, and never flashes:

```bash
python3 tools/build-release.py "$BASE" local/A9AccessibilityService.apk
```

Add `--ir --vendor-image "$VENDOR" --aosp-headers "$AOSP_HEADERS"` for the IR
HAL, and `--xrz` to add the experimental XRZ v2 overlay after the base or IR
image. IR and XRZ both require the matching stock vendor image. Release signing
uses the same optional signing environment variables as `build-apk.sh`.

The manual build below remains supported and exposes each intermediate step.

```bash
cd "$HOME/HibreakProPatchingService"
tools/build-apk.sh local/A9AccessibilityService.apk build/HiBreakEink-release.apk
tools/build-daemon.sh build/a9_eink_server-release
```

Stop on an error. On success, build the display/AOD release base:

```bash
tools/patch-gsi.sh "$BASE" build/HiBreakPro-release-base.img \
  build/HiBreakEink-release.apk build/a9_eink_server-release --release
```

Do not add an ADB key or `--root`. These scripts refuse existing output
files: when rebuilding, choose new output names consistently rather than
deleting your only known-working image.

**Optional IR:** follow [Add IR support to an image](ir-overlay.md) now,
then return here to select the final image.

**Optional XRZ v2:** follow the [experimental graphics-property overlay](xrz-overlay.md)
after IR, if included, or directly after the display/AOD base. Set `XRZ_SOURCE`
to the resulting **pre-XRZ** image. This corrects four property labels and
restores the stock composer's set permission; it is not a proven crash fix.
Do not rebuild on top of a previous XRZ output.

## Experimental source-built APK

After installing the [source-APK prerequisites](inputs.md#experimental-source-apk-prerequisites),
the orchestrator can build from the checked-in Kotlin and resources instead of
the upstream APK:

```bash
python3 tools/build-release.py "$BASE" --source-apk
```

Do not pass a base APK with `--source-apk`. The manifest identifies this option
and records checksums of the source and build files. To build just the APK:

```bash
tools/build-source-apk.sh build/HiBreakEink-source-experimental.apk
```

Both commands use the same signing variables and overwrite safeguards as the
patched-APK route. With no signing variables they use a debug certificate.
This route is **experimental**: host checks do not establish device behavior or
complete parity with the patched APK. Keep using the supported patched-APK
route for release images until the [device checks](tests.md) have passed.

## Select and check the final image

Choose **one**:

```bash
# With XRZ v2 (with or without IR, according to XRZ_SOURCE):
export IMAGE="$PWD/build/HiBreakPro-xrz-v2-test.img"
```

```bash
# With IR, without XRZ:
export IMAGE="$PWD/build/HiBreakPro-release-ir.img"
```

```bash
# Without IR or XRZ:
export IMAGE="$PWD/build/HiBreakPro-release-base.img"
```

```bash
e2fsck -fn "$IMAGE"
sha256sum "$IMAGE"
```

Stop if the filesystem check fails. Save the checksum alongside any image
you distribute. Also publish the exact required stock firmware/vendor
version and the GSI version used, plus the test status. Recipients must
check their installed stock vendor baseline before flashing; installing a
GSI does not automatically update vendor. Do not advertise compatibility
with older/newer firmware without separate validation on that combination.
`--release` makes a **release candidate**: it does not sign
the whole ROM for verified boot/OTA, change every upstream debug setting, or
grant redistribution rights. Test the final image before distributing it.
See [release caveats](../reference/patcher.md).

**Building never flashes a phone.** Stop here if you only wanted an image.
