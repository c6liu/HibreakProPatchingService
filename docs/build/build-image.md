# Build a release image

Return to the project folder. Use the same terminal in which you set the
variables. If you opened another one, set `ANDROID_NDK_HOME` and `BASE`
([inputs](inputs.md)), the three [signing variables](signing.md) and, for IR,
`VENDOR` and `AOSP_HEADERS` ([IR inputs](ir-inputs.md)) again.

For a single-command release build, use the orchestrator. It creates a new
timestamped directory under `build/`, writes a `manifest.json` with
input/output checksums, and never flashes. Only the final image is retained;
intermediate stage images are temporary. Independent APK, daemon, and (when
requested) IR HAL builds run concurrently before image patching:

```bash
python3 tools/build-release.py "$BASE"
```

By default this **builds and signs the source APK**, compiles the
daemon, and creates the release image. Set the [signing variables](signing.md)
first for release signing; otherwise the APK is debug-signed. Passwords are
entered only at the signer's terminal prompts.

Add `--ir --vendor-image "$VENDOR" --aosp-headers "$AOSP_HEADERS"` for the IR
HAL, and `--xrz` to add the experimental XRZ v2 overlay after the base or IR
image. IR and XRZ both require the matching stock vendor image. Release signing
uses the same optional signing environment variables as `build-source-apk.sh`.

### One command with IR and the property overlay

Set `BASE`, `VENDOR` (the matching raw stock vendor image),
`ANDROID_NDK_HOME`, `AOSP_HEADERS`, and optionally `SECILC` to your installed
policy compiler. Then run:

```bash
python3 tools/build-release.py "$BASE" --ir --xrz
```

Use a Python interpreter with SETools installed for XRZ; for example, on a host
where the system Python provides SETools, use `/usr/bin/python3` instead of
`python3`. The same interpreter runs both overlays.

All paths can also be supplied explicitly:

```bash
/usr/bin/python3 tools/build-release.py "$BASE" --ir --xrz \
  --vendor-image "$VENDOR" \
  --ndk "$ANDROID_NDK_HOME" \
  --aosp-headers "$AOSP_HEADERS" \
  --secilc "$SECILC"
```

This builds the APK and daemon, then applies the requested image stages in
order. Intermediate stage images are removed after the build, and the final
image is always named `HiBreakPro-release.img`. The compiler selection is
passed to **both** overlays. Use the printed final image path (or
`final_image` in the manifest).

To reuse a signed source APK you already built, without rebuilding or signing it:

```bash
/usr/bin/python3 tools/build-release.py "$BASE" --built-apk build/HiBreakEink.apk \
  --ir --xrz
```

The existing APK is copied unchanged and its signature/alignment verified with
uber-apk-signer. When `APK_RELEASE_CERT_SHA256` is set, the certificate must
match it. No keystore password is needed for reuse. The manifest records the
original APK checksum; it does not claim that current source files produced it.
Do not combine `--source-apk` and `--built-apk`. Positional APK inputs are rejected.

The manual build below remains supported and exposes each intermediate step.

## Manual source-APK build

```bash
cd "$HOME/HibreakProPatchingService"
tools/build-source-apk.sh build/HiBreakEink-release.apk
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

## Source-built APK

After installing the [source-APK prerequisites](inputs.md#source-apk-prerequisites),
the orchestrator builds from the checked-in Kotlin and resources by default.
The explicit equivalent remains available:

```bash
python3 tools/build-release.py "$BASE" --source-apk
```

The upstream APK patcher has been removed. The manifest identifies source builds
and records checksums of the source and build files. To build just the APK:

```bash
tools/build-source-apk.sh build/HiBreakEink-source.apk
```

Both commands use the same signing variables and overwrite safeguards.
With no signing variables they use a debug certificate. Host checks do not
establish physical display behavior; complete the [device checks](tests.md)
before distributing a release image.

## Select and check the final image

For the unified builder, set `IMAGE` to its printed **Final image** path in
the new timestamped directory. The manifest's `final_image` names that same
file. Keep the manifest with the image; intermediate base/IR images are not
the final output when later stages were requested.

For the manual commands above, choose **one**:

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
