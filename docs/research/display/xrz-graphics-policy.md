# Stock versus GSI graphics policy

## Current status

The [XRZ v2 overlay](../../build/xrz-overlay.md), enabled by default for the
tested release inputs, covers four exact
properties: `vendor.xrz.fps_limit`, `vendor.xrz.gray_256_dither`,
`vendor.xrz.hwc_idle`, and `ro.vendor.xrz.screen_type`. On the tested
3.1.6/EvoX 11.11 phone, label selection and loaded composer read/set grants
were confirmed with SELinux enforcing. The short v2 snapshot contained no
composer crash or framework restart, but actual property publication, panel
type, and long-term stability remain unverified. It is not a proven fix for
the [native composer crash](composer-crash.md).

The sections below preserve the v1-to-v2 investigation chronologically.

## Initial host comparison (v1)

Host-side comparison on 2026-11-04 used the backed-up 3.1.6 stock vendor
and stock system images with the EvoX 11.11 microG release system image.
No phone was connected for this comparison.

- Stock platform property contexts label `vendor.xrz.*`,
  `persist.vendor.xrz.*`, `ro.vendor.xrz.*`, and `pm.boot.*` as
  `vendor_xrz_prop`. The stock vendor policy version is `31.0` and grants
  `hal_graphics_composer_default` read and property-service `set` on the
  versioned `vendor_xrz_prop_31_0` attribute.
- The EvoX GSI lacks that type's mapping in its `31.0.cil` and labels the
  three observed graphics properties through generic `vendor_default_prop`.
  Adding only the missing mapping and labels would deny existing reads for
  203 domains and existing property sets for four domains on this build.
- A host-only experiment with the new
  [XRZ compatibility overlay](../../../tools/image/add-xrz-compat-to-gsi.py) preserves
  all 847 baseline effective `allow` permission tuples on those exact three
  properties and adds only the composer's property-service `set`. It adds
  no new neverallow violations to this merge. The EvoX/vendor merge already
  reports 1,750 parsed neverallow diagnostics; the experiment does not fix them.
  These checks do not prove the phone loads the intended policy or contexts.
- The vendor's precompiled platform-policy digest begins `0a8c1705`; the
  display-only EvoX image's digest begins `223c0e9a` and the IR-enabled
  image's begins `294e6f90`. Under the standard Android init cache check,
  even the display-only image's mismatch should cause policy recompilation.
  Therefore the user's improved stability with the IR build cannot be
  attributed to forcing recompilation from these hashes alone.

The original v1 overlay changed three exact property names and was opt-in. The
native graphics crash and the report of improved stability remain unresolved:
actual property writes, new AVCs, and sleep/wake and scrolling behavior must
be tested on-device before claiming any fix.

## First on-device XRZ check (2026-11-04)

After the user flashed the experimental image, read-only inspection at about
13:43 EST confirmed stock vendor fingerprint build `1772711616`, slot A,
SELinux **Enforcing**, and all three overlay markers. `getprop -Z` selects
`vendor_xrz_prop` for the three target properties. The kernel's loaded policy
was readable over ADB; offline inspection confirmed the versioned mapping,
the composer's file-read/property-set grants, and retained system_server
read access. Thus these are active device settings, not just image contents.

At approximately nine minutes of kernel uptime, the retained crash buffer
contained only the previously documented boot-time forked-init `SIGABRT`.
There was no composer tombstone and Dropbox had no `SYSTEM_RESTART` entry.
No target-property composer set denial appeared in the captured logs.
This limited observation does not establish successful writes or long-term
stability, and no controlled sleep/wake or scrolling test was performed.

Reading the three values with ordinary shell `getprop` was denied; the empty
output is **not** evidence that the properties are unset. The inspection
itself produced these shell read AVCs. The loaded policy lacks shell read
access, consistent with the host's generic-property baseline, so these AVCs
alone do not demonstrate a new runtime regression.

One additional startup mismatch is now directly observed: at 13:34:51.156,
the composer was denied `set` on `ro.vendor.xrz.screen_type`, still labelled
`vendor_default_prop`. The v1 three-property overlay deliberately did not
cover it. This prompted the writer/reader investigation below; a missing
write is not a proven crash cause.

Local evidence is in `build/xrz-device-20261104-1343/`, including the loaded
policy, property metadata, crash/all-buffer logs, SurfaceFlinger snapshot,
and Dropbox restart query. These diagnostics may contain personal data and
are not committed. No settings, service restarts, power transitions, or
reboots were requested during this inspection.

## Screen-type writer and readers (2026-11-04)

Further offline analysis of the stock 3.1.6 `hwcomposer.mt6877.so` established:

- `mtk_init()` issues ioctl `0xc00464d0` and stores its integer result as the
  panel type. At library address `0xf0f80`, it converts that result to a decimal
  string, then calls `property_set("ro.vendor.xrz.screen_type", value)` at
  `0xf0fac`. This is a hardware-derived publication, not a missing static
  build-property default. The code logs an ioctl error if appropriate but
  still publishes the result; permitting the write does not validate the ioctl.
- `CommitPolicy::setCommitInfoForJob()` reads the same property at `0xf015c`.
  The helper `get_property_int_value()` uses `property_get` with default `"0"`
  and converts it with `atoi`. At `0xf02e8`, the value's `> 0` test controls a
  commit-info field (`0` or `2`). Its physical effect was not established.
- Stock framework DEX code contains readers in `XrzEinkManager` and
  `HandwrittenClient`. The inspected EvoX `framework.jar` and `services.jar`
  DEX files contain no reference to this exact property. This is not an
  exhaustive scan of every app or native library.

The phone's actual panel-type integer could not be established read-only:
startup composer log lines were no longer retained and the ADB shell cannot
read the relevant debugfs directory. Do not infer a color/monochrome enum
value or hard-code one. If the measured value is zero, the commit branch may
remain the same as the missing-property fallback.

XRZ overlay **v2** adds only the exact `ro.vendor.xrz.screen_type` context to
the original three properties and retains the same versioned mapping and
effective-permission checks. Rebuild from the pre-XRZ IR/display image; do not
stack it on v1. It does not change the vendor binary or prepopulate the
read-only property. A later on-device boot must confirm the writer succeeds;
no crash fix or visual improvement is claimed from the static analysis.

The separate EvoX IR + XRZ v2 image was built and its persisted merged policy
recompiled successfully. It preserves the same 847 baseline effective allow
tuples on the relabelled type; composer `set` is still the sole addition.
All 17 focused IR/XRZ tests and an independent `e2fsck -fn` passed. The v1
image is rejected as a build input. At this build-validation stage no v2
flashing or device reboot had been performed; the user's subsequent flash is
recorded below. Existing base-policy neverallow diagnostics remain unchanged.

Native disassembly and framework analysis are kept locally in
`build/xrz-screen-type-analysis/`, not committed or redistributed.

## First on-device v2 check (2026-11-04)

After the user flashed v2, read-only inspection at 13:58 EST (about 78 seconds
of kernel uptime) confirmed both v2 context/mapping markers, slot A, the same
stock vendor fingerprint, and SELinux **Enforcing**.
`getprop -Z ro.vendor.xrz.screen_type` selected `vendor_xrz_prop`.
The loaded kernel policy retained the composer's read/set grants. Its SHA-256
matched the v1 loaded policy, as expected: v2 changes property selection,
not the effective compiled access rules.

The captured buffers contained no screen-type set denial and no failure for
the other three target properties. They contained only the known forked-init
boot `SIGABRT` in the crash buffer, no composer crash, and no Dropbox
`SYSTEM_RESTART`. However, panel discovery logs were not retained and audit
rate limiting reported lost events. Therefore neither the actual panel-type
integer nor successful publication is proven by this snapshot; absence of
denials alone is insufficient. No controlled sleep/wake or scrolling test
was performed, and no device state was changed.

Evidence is local in `build/xrz-v2-device-20261104-1358/`. Continued stability
and physical display behavior still need user testing.

## Background: composer property denials

Before the XRZ overlay, the stock compositor (`hal_graphics_composer_default`) repeatedly failed to
set `vendor.xrz.fps_limit`, `vendor.xrz.gray_256_dither` and
`vendor.xrz.hwc_idle`. The GSI labels them `vendor_default_prop`; stock vendor
policy only allows the versioned `vendor_xrz_prop_31_0`. These denials flood
the rate-limited audit log (thousands lost per boot) and hide other denials.
Adding `vendor_xrz_prop` labels to `plat_property_contexts` was tried and did
not stop them, because the GSI's `mapping/31.0.cil` does not link the type to
`vendor_xrz_prop_31_0`; it also caused new app read denials, so it was
reverted.
