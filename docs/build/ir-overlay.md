# Add IR support to an image

Skip this page for display-only builds. You need the release base from
[Build a release image](build-image.md), plus `VENDOR`, `AOSP_HEADERS` and
`ANDROID_NDK_HOME` from [Prepare IR build inputs](ir-inputs.md).

```bash
tools/build-ir-hal.sh build/consumerir.hxd-release.so
python3 -m unittest tools.tests.test_hxd_nec tools.tests.test_hxd_learn \
  tools.tests.test_ir_overlay tools.tests.test_ir_remote
```

Check the tests pass without missing-dependency skips. First run the IR
preflight; **this command does not create an image**:

```bash
python3 tools/add-ir-capture-to-gsi.py \
  build/HiBreakPro-release-base.img build/HiBreakPro-release-ir.img \
  --hal-module build/consumerir.hxd-release.so \
  --vendor-image "$VENDOR" --secilc secilc --check-only
```

If it succeeds and you are ready to package, run it without `--check-only`:

```bash
python3 tools/add-ir-capture-to-gsi.py \
  build/HiBreakPro-release-base.img build/HiBreakPro-release-ir.img \
  --hal-module build/consumerir.hxd-release.so \
  --vendor-image "$VENDOR" --secilc secilc
```

Start from the clean release base, not an old IR test image. This installs
the NEC adapter, its init action and scoped SELinux policy. It does **not**
include either test app, capture/camera services or private IR request hooks.
Do not add `--diagnostics-binary`, `--remote-apk`, or `--api-test-apk` to a
normal release build. Development opt-ins are described in
[Overlay details](#overlay-details-and-development-options).

The policy preflight counts both ordinary `neverallow` and extended-permission
`neverallowx` conflicts (such as ioctl restrictions). It rejects new conflicts
of either kind introduced by the overlay. Existing conflicts are not fixed;
compilation uses Android init's runtime `-N` option to skip these assertions.
This does not disable runtime SELinux enforcement or prove that the upstream
ROM is production-ready.

Then continue at
[Select and check the final image](build-image.md#select-and-check-the-final-image).

### Host-only baseline reduction experiment (2026-11-11)

The EvoX 11.11 microG 20260920 GSI with stock 3.1.6 vendor policy has
1,750 ordinary and 24 extended-permission diagnostics: **1,774 total**.
Separate extracted-policy candidates produced these results without changing
either image:

| PHH grant removal | Allow rules removed | Ordinary | Extended | Total |
| --- | ---: | ---: | ---: | ---: |
| None (baseline) | 0 | 1,750 | 24 | 1,774 |
| Broad `phhsu_daemon` property-service set | 1 | 1,262 | 24 | 1,286 |
| Above plus broad hardware-service access | 3 | 941 | 24 | 965 |
| All ordinary-diagnostic-identified PHH `phhsu_daemon` grants | 70 | 371 | 15 | 386 |

Only selected `allow` statements were removed; assertions, type declarations,
other domains' grants, and permissive-domain declarations were unchanged.
All candidates compiled with `-N`, but none compiled successfully with
assertion checking enabled. These are diagnostic counts, not independent
vulnerability counts, and the candidates have not been tested on a phone.

The upstream system-ext policy already declares `phhsu_daemon` permissive.
Leaving that declaration intact means removing its explicit grants is not
equivalent to restricting its runtime access. Conversely, making it enforcing
would require a separately reviewed root permission set and device regression
tests. These reductions are **not automatically applied by the image builder**;
they demonstrate a feasible cleanup direction, not a hardened release policy.

## Overlay details and development options

The display patcher does not include IR automatically. Build the NEC
adapter using NDK and the public AOSP headers described in
[Prepare IR build inputs](ir-inputs.md). The adapter's contract is in the
[IR adapter reference](../reference/ir-adapter.md).
The IR overlay additionally requires host `readelf` from `binutils` and
`secilc`. Start with a display-patched release image **without any prior
IR overlay**.

`--vendor-image` is required for IR, including preflight, but not for a
display-only build. Supply a raw vendor image matching the firmware
installed on the **target phone**. The overlay uses its SELinux policy
and mapping version for merge validation and checks the stock IR
module/service; it does not bundle or flash vendor.
The documented baseline is stock **3.1.6 /
`Bigme_HiBreak_V1.0_20260306`**. A release validated against that vendor is
not established to work on older or newer stock firmware, even on the
same model. The offline tool cannot verify a recipient's installed firmware.
A successful preflight, or rebuilding with another vendor image, does not
replace device testing of that firmware/kernel/GSI combination.
Publish the required stock firmware/vendor and GSI versions with every
release image and checksum. Do not claim other firmware versions supported
without separate validation.

```bash
export ANDROID_NDK_HOME=/path/to/android-ndk
export AOSP_HEADERS=/path/to/aosp-include
bash tools/build-ir-hal.sh build/consumerir.hxd.so

# Preflight only: compiles/validates policy and the module, produces NO image.
python3 tools/add-ir-capture-to-gsi.py \
  build/HiBreakPro-release.img build/HiBreakPro-release-ir.img \
  --hal-module build/consumerir.hxd.so \
  --vendor-image /path/to/matching-stock-vendor.img \
  --secilc /path/to/secilc --check-only
```

When ready to package, run that overlay command again **without**
`--check-only`. It refuses to overwrite an existing output. The release
configuration installs only the NEC adapter, its init bind-mount action,
and its scoped SELinux policy/file context. It does **not** install either
test app, `hxd-learn`, capture/camera services, private IR properties,
or their app-domain policy. No diagnostic binary or APK is required to
build this configuration. Stock vendor is read-only and unchanged.

Development-only opt-ins (omit all from the release command):

- `--diagnostics-binary build/hxd-learn`: adds capture/camera diagnostics
  and their service/policy. Build with `tools/build-ir-tool.sh`.
- `--remote-apk build/HiBreakIrRemote.apk`: adds the privileged, fixed
  TCL test app/service; **requires** `--diagnostics-binary`. Build with
  `tools/build-ir-remote.sh`.
- `--api-test-apk build/AndroidIrApiTest.apk`: adds the ordinary Android
  API test app under `/system/app`, independently of capture diagnostics.
  Build with `tools/build-ir-api-test.sh`. Alternatively sideload it only
  on a development device.

The old optional positional `hxd-learn` argument is deprecated and prints a
warning; it remains accepted for compatibility. Use `--diagnostics-binary`
instead. Do not layer onto v4-v8 test images to produce a release: start from
the clean release base.
On a previously used development device, an APK installed in userdata
may remain after changing system images; inspect/uninstall test packages
separately rather than assuming an update wipes userdata.

The retained NEC support is limited to one NEC/NECext frame at nominal
38000/38222 Hz; both select the controller's same built-in carrier.
Releasing this overlay does not make arbitrary waveforms/repeats supported,
measure carrier accuracy, or remove the upstream GSI's release caveats.
