# Build a release image

Return to the project folder. Use the same terminal in which you set the
variables. If you opened another one, set `ANDROID_NDK_HOME` and `BASE`
([inputs](inputs.md)), the three [signing variables](signing.md),
`VENDOR` and `AOSP_HEADERS` ([IR inputs](ir-inputs.md)) again.

For a single-command release build, use the orchestrator. It creates a new
timestamped directory under `build/`, writes a `manifest.json` with
input/output checksums, and never flashes. Only the final image is retained;
intermediate stage images are temporary. Independent APK, daemon, and (when
requested) IR HAL builds run concurrently before image patching:

```bash
python3 tools/build-release.py "$BASE"
```

By default this **builds and signs the source APK**, adds IR and XRZ,
uses property-only refresh and the working init bridge for Auto Refresh and
Anti-Shake, applies the experimental PHH grant reduction, and migrates the
e-ink daemon and display/AOD helpers to enforcing domains. The PHH root
domain itself remains permissive; the reduction is not a hardening claim.
Set the [signing variables](signing.md) for release signing; otherwise the
APK is debug-signed. Passwords are entered only at the signer's terminal prompts.

The migration defaults are restricted to the tested EvoX GSI (SHA-256
`d25aeac2b42012e76e8f4fd95d69f9e28ceeac64289d85f194d72ef0249374bf`)
and HiBreak Pro 3.1.6 vendor image (SHA-256
`6ba5354d8bcd1b1b91cfc79c3cbe148ddd31df706e0aa6c6e03191f9dcff24ff`).
Freshly generated intermediate images are checked against the tested
policy-critical components and service metadata and undergo the existing
policy checks. The component checks are not a whole-image identity check:
use the release builder to generate the intermediates rather than supplying
an unrelated or independently modified image. A different
GSI or vendor fails explicitly instead of silently disabling features.
Use a Python interpreter with SETools, such as `/usr/bin/python3` where
the system Python provides it.

### Default build

Set `BASE`, `VENDOR` (the tested raw stock vendor image),
`ANDROID_NDK_HOME`, `AOSP_HEADERS`, and optionally `SECILC` to your installed
policy compiler. Then run:

```bash
python3 tools/build-release.py "$BASE"
```

All paths can also be supplied explicitly:

```bash
/usr/bin/python3 tools/build-release.py "$BASE" \
  --vendor-image "$VENDOR" \
  --ndk "$ANDROID_NDK_HOME" \
  --aosp-headers "$AOSP_HEADERS" \
  --secilc "$SECILC"
```

The stages run in order; intermediate images are removed and their checksums
are recorded in the manifest. The final image is always
`HiBreakPro-release.img`. Use the printed final image path (or `final_image`
in the manifest).

### Compatibility and opt-outs

Use `--compatibility` for another GSI to turn off all tested-device defaults
and retain the legacy base release behavior. Explicit `--ir`, `--xrz`,
`--experimental-phh-reduction` and `--experimental-property-only-refresh`
can be added back where their own checks permit them. IR needs headers and a
vendor image; XRZ and PHH reduction also need a vendor image. Some overlays
remain restricted to their tested policy inputs.

Individual defaults can be disabled with `--no-enforcing-migration`,
`--no-init-eink-bridge`, `--no-ir`, `--no-xrz`,
`--no-experimental-phh-reduction`, or
`--no-experimental-property-only-refresh`. The enforcing migrations require
the init bridge, and the tested bridge requires IR, XRZ, PHH reduction and
property-only refresh: disable dependent features as well, or use
`--compatibility`. The legacy property-only Auto Refresh experiment is
known not to work and cannot be combined with the init bridge.

To reuse a signed source APK you already built, without rebuilding or signing it:

```bash
/usr/bin/python3 tools/build-release.py "$BASE" --built-apk build/HiBreakEink.apk
```

The existing APK is copied unchanged and its signature/alignment verified with
uber-apk-signer. When `APK_RELEASE_CERT_SHA256` is set, the certificate must
match it. No keystore password is needed for reuse. The manifest records the
original APK checksum; it does not claim that current source files produced it.
Do not combine `--source-apk` and `--built-apk`. Positional APK inputs are rejected.

The manual build below remains supported and exposes each intermediate step.

### Experimental property-only refresh test

With `--compatibility`, add `--experimental-property-only-refresh` to build
the legacy property-only refresh test image.
Only the daemon's refresh-mode write to `eink_debug/global_mode` is omitted;
it still sets `vendor.xrz.global_refresh_mode`, and Auto Refresh and
Anti-Shake retain their existing debugfs writes. The default tested build
instead uses the init bridge for those controls and enforcing domains.
The option is recorded in the manifest. No build command flashes a device.

Keep a working image and recovery path before testing. Compare all five modes
(especially HD_256), app switching, sleep/wake, and Auto Refresh/Anti-Shake
against the working image. `adb logcat -s a9EinkService:I '*:S'` shows
`Property-only refresh test: requested ...` when a property request succeeds
and an error if setting it fails; that log confirms neither composer receipt
nor physical panel behavior. See the [investigation](../reference/verification.md#debugfs-alternative-investigation-2026-11-11).

### Experimental property-only Auto Refresh test

With `--compatibility`, add `--experimental-property-only-auto-refresh` to replace the daemon's
`clean_a2` write with `vendor.xrz.auto_clean_enabled=0/1`. It can be combined
with `--experimental-property-only-refresh`. Anti-Shake still uses its
original debugfs path. The manifest records
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

Without `--rebuild-gsi`, the standalone experiment starts from the byte-identical tested
IR/XRZ/PHH-reduced image with property-only refresh (SHA-256
`e04bb8354ffcf2a999945bc83fe1d834caa1c131bfe3574353d1939134ee70e2`).
It builds a new daemon and has init write the two existing Auto Refresh and
Anti-Shake nodes using fixed `0`/`1` requests. It does not by itself migrate
the daemon out of `phhsu_daemon`; the default release build applies the
enforcing migrations afterward.

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

### Experimental enforcing e-ink daemon

Without `--rebuild-gsi`, the standalone migration overlay accepts only the
user-tested init-bridge image (SHA-256
`5844ef262b47d04cd3df990b3e97e71567a940ff85f8322348a6ce3ee722cdca`)
and the matching vendor image. It installs an enforcing e-ink daemon domain,
the existing tested display bridges, exact frontlight labels, and socket peer
authentication. It does **not** migrate display/AOD helpers or other PHH
services, and does not retire `phhsu_daemon`.

```bash
/usr/bin/python3 tools/add-eink-migration-to-gsi.py \
  "$TESTED_BRIDGE_IMAGE" "$NEW_TEST_IMAGE" \
  --vendor-image "$VENDOR" --ndk "$ANDROID_NDK_HOME" --secilc "$SECILC"
```

The tool refuses to overwrite an image or manifest and never flashes. Keep the
working bridge image and recovery path. After a separately authorized flash,
confirm `adb shell getenforce` reports `Enforcing` and
`adb shell 'ps -AZ | grep a9_eink'` shows `u:r:hibreak_eink:s0`. Check
`adb logcat -b all -s a9EinkService:V A9SideKeys:V init:I auditd:V '*:S'`
for rejected socket clients, package-registry errors, init action failures,
and AVC denials. Exercise both frontlights, all refresh modes, Auto Refresh,
Anti-Shake, per-app switching, sleep/wake, AOD, custom side keys, DPAD and
theme settings. The policy and DAC checks do not prove framework authorization
or physical behavior; request-property success is not a hardware-write
acknowledgement.

### Experimental enforcing display and AOD helpers

Without `--rebuild-gsi`, the standalone overlay starts from the user-tested Binder-callback e-ink
daemon image (SHA-256
`6077c0eee9b37038ac35d5f3b08106aa3280b29073787c41404a72666fbd8bff`):

```bash
/usr/bin/python3 tools/add-display-migration-to-gsi.py \
  "$TESTED_EINK_IMAGE" "$NEW_TEST_IMAGE" \
  --vendor-image "$VENDOR" --secilc "$SECILC"
```

It moves all five HiBreak display/AOD services into an enforcing
`hibreak_display` domain. AOD inversion is retained; the migration imports
existing setup/inversion markers into separate, scoped persistent state
properties. The existing AOD toggle and original property labels remain
unchanged. The default release build includes this migration. It does not
migrate upstream PHH services or remove `phhsu_daemon`.

The builder never flashes. Keep the prior image and recovery path. After an
authorized flash, check `adb shell getenforce` and collect
`adb logcat -b all -s hibreak-display:V auditd:V init:I '*:S'`. Test boot
display, screen wake, AOD on/off, inversion on doze and restoration on wake,
and user-enabled inversion. Also retest frontlights, refresh modes and side
keys. The helpers are short-lived, so their domain may not appear in a later
process listing; look for `hibreak_display` in AVCs if a helper fails.

### Experimental PHH grant reduction

The default build applies the exact 70-grant host experiment after IR and XRZ,
before the bridge and enforcing migrations. It requires `--vendor-image` and `--secilc`, accepts
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

This removes substantial root permissions,
including daemon entrypoint access, but preserves the upstream permissive
`phhsu_daemon` declaration. It is **not hardening**, still requires `-N`,
and does not make all upstream services enforcing. Keep your working image and recovery path;
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
