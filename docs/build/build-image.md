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

### Experimental property-only refresh test

Add `--experimental-property-only-refresh` to build a separate test image.
Only the daemon's refresh-mode write to `eink_debug/global_mode` is omitted;
it still sets `vendor.xrz.global_refresh_mode`, and Auto Refresh and
Anti-Shake retain their existing debugfs writes. Normal builds are unchanged.
The option is recorded in the manifest. This is not an enforcing-domain
migration or a proven equivalent refresh path. The image is never flashed
by the build command.

Keep a working image and recovery path before testing. Compare all five modes
(especially HD_256), app switching, sleep/wake, and Auto Refresh/Anti-Shake
against the working image. `adb logcat -s a9EinkService:I '*:S'` shows
`Property-only refresh test: requested ...` when a property request succeeds
and an error if setting it fails; that log confirms neither composer receipt
nor physical panel behavior. See the [investigation](../reference/verification.md#debugfs-alternative-investigation-2026-11-11).

### Experimental property-only Auto Refresh test

Add `--experimental-property-only-auto-refresh` to replace the daemon's
`clean_a2` write with `vendor.xrz.auto_clean_enabled=0/1`. It can be combined
with `--experimental-property-only-refresh`. Anti-Shake still uses its
original debugfs path; normal builds are unchanged. The manifest records
each experiment separately. This does not migrate the daemon to an enforcing
domain, and the property is not proven equivalent to `clean_a2` on this device.
The user reported that Auto Refresh did not seem to work in the 2026-11-11
device test, despite successful property requests. Do not use this experiment
as a replacement for the existing control.

Keep the previous working image and recovery path. Compare Auto Refresh on
and off in the same apps and refresh modes against the previous image, including
app changes and sleep/wake. Look for changes in ghosting and cleaning; absence
of visible differences alone does not establish equivalence. The daemon log
`Property-only auto-refresh test: requested ...` confirms a property set, not
composer receipt or panel behavior. Failures are logged as
`Failed to set vendor.xrz.auto_clean_enabled=...`.
See the [Color comparison](../reference/verification.md#hibreak-pro-color-comparison-2026-11-11).

### Experimental init e-ink bridge

This separate experiment starts from the byte-identical tested
IR/XRZ/PHH-reduced image with property-only refresh (SHA-256
`e04bb8354ffcf2a999945bc83fe1d834caa1c131bfe3574353d1939134ee70e2`).
It builds a new daemon and has init write the two existing Auto Refresh and
Anti-Shake nodes using fixed `0`/`1` requests. It does not change the default
release builder or migrate the daemon out of `phhsu_daemon`.

```bash
/usr/bin/python3 tools/add-eink-init-bridge-to-gsi.py \
  "$TESTED_IMAGE" "$NEW_TEST_IMAGE" \
  --vendor-image "$VENDOR" --ndk "$ANDROID_NDK_HOME" --secilc "$SECILC"
```

The tool refuses to overwrite an image or manifest and never flashes. Keep
the previous working image and recovery path. After boot, observe
`adb logcat -b all -s a9EinkService:I init:I '*:S'` while testing toggles,
rapid changes, repeated settings, app changes and sleep/wake. Daemon request
success is not hardware-write acknowledgement; init logs failed actions.
Compare actual panel behavior against the previous image. SELinux remains
enforcing globally, but `phhsu_daemon` remains permissive.

### Experimental PHH grant reduction

Add `--experimental-phh-reduction` to apply the exact 70-grant host experiment
after all other overlays. It requires `--vendor-image` and `--secilc`, accepts
only the byte-identical EvoX 11.11 20260920 system-ext policy, and rejects a
merge that does not produce 371 ordinary plus 15 extended conflicts.
The final image remains `HiBreakPro-release.img`; the manifest explicitly
records the experimental option and reduction-tool checksum.

```bash
/usr/bin/python3 tools/build-release.py "$BASE" --built-apk build/HiBreakEink.apk \
  --ir --xrz --experimental-phh-reduction \
  --vendor-image "$VENDOR" --aosp-headers "$AOSP_HEADERS" \
  --ndk "$ANDROID_NDK_HOME" --secilc "$SECILC"
```

Default builds are unchanged. This removes substantial root permissions,
including daemon entrypoint access, but preserves the upstream permissive
`phhsu_daemon` declaration. It is **not hardening**, still requires `-N`,
and has not been device-validated. Keep your working image and recovery path;
do not make this domain enforcing without reviewing its required grants.
See the [host experiment](ir-overlay.md#host-only-baseline-reduction-experiment-2026-11-11).
The standalone [overlay tool](../../tools/add-phh-reduction-to-gsi.py)
also supports `--check-only` without producing an image.

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
