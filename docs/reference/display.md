# Device and display configuration

- MediaTek Dimensity 900 / MT6877, `k6877v1_64_k419`, kernel **4.19.191**.
- Stock vendor from the device's 3.1.6 backup; build identified as
  `Bigme_HiBreak_V1.0_20260306`. Vendor fingerprint identifies Android 12,
  `SP1A.210812.016`, build `1772711616`; the marketing OS version can differ.
- Display **824 x 1648**, density 300, reported 60 Hz. That is the Android
  compositor's mode, not a measured 60 Hz physical e-ink refresh rate.
- Rotated HWC client target **1648 x 824 RGBA_8888**, pixel stride 1648,
  byte pitch 6592; `ORIENTATION_270`. Do not blindly change stride/rotation.
- vbbot Evolution X 10.5 (20250507) worked with stock vendor.
- Android 16 LineageOS SU 23.2 (2026.10.10) worked with stock vendor after
  disabling HWC overlays and both SurfaceFlinger backpressure settings.
- Rootless EvoX 11.11 microG (20260920) worked after those fixes were made
  persistent using root init services. No Magisk or interactive `su` is needed.
- Five-mode APK and AOD-switch UI were installed and exercised. The rebuilt
  daemon accepts Hyper and AOD commands, but physical speed improvements and
  every AOD edge case have not been independently measured.

## Optional display tweaks

- Refresh modes are per application by default. Enable **Disable Per-App
  Refresh Mode** in **Eink Settings → Eink Accessibility Service** to use
  one global refresh mode.
- In **Phh Treble Settings** (**Treble Settings** on the tested GSI), enable:
  - **Mediatek settings → Mediatek GED KPI support**.
  - **Display settings → Disable SF GL backpressure**.
  - **Display settings → Disable SF HWC backpressure**.
- Reboot after changing the Treble settings. Both backpressure settings are
  already disabled at boot by the patched image; the toggles align the
  Treble Settings preferences with that configuration.
- Optionally select **High** in Android **Settings → Accessibility →
  Color contrast** for higher-contrast interface colors. This does not
  adjust the physical panel's contrast or black/white points.

For the complete setup sequence, see [first-boot setup](../install/first-boot-setup.md).
These preferences do not replace **Display settings → Disable HW overlays**,
which is required to keep GPU composition enabled as described below.

## Display: the working recipe

Keep the stock vendor. Set both persistent phh backpressure properties and
their `debug.sf` counterparts to `false` before SurfaceFlinger starts:

```text
persist.sys.phh.enable_sf_gl_backpressure
persist.sys.phh.enable_sf_hwc_backpressure
debug.sf.enable_gl_backpressure
debug.sf.enable_hwc_backpressure
```

Force GPU/client composition rather than the vendor device-composition path.
This does not disable the physical panel's vendor HWC driver. SurfaceFlinger
forgets the override on restart, so init re-applies it.

The tested enforcing migration selects `hibreak-disable-hwc.sh --aidl`,
which calls `service call SurfaceFlingerAIDL 65 i32 1`. Transaction 65 was
verified from this exact EvoX compositor's `forceClientComposition(bool)`
proxy and tested on the physical phone. It is not a portable AIDL transaction
number: do not use it on an unverified compositor. Compatibility builds keep
the legacy `service call SurfaceFlinger 1008 i32 1` path.

The root-enabled diagnostic that originally fixed the screen was:

```bash
adb shell su 0 setprop persist.sys.phh.enable_sf_gl_backpressure false
adb shell su 0 setprop persist.sys.phh.enable_sf_hwc_backpressure false
adb shell su 0 setprop ctl.restart surfaceflinger
adb shell su 0 service call SurfaceFlinger 1008 i32 1
```

Do not use that recipe unchanged on a rootless GSI: `su` is absent. The
checked-in init services run as **uid 0**, in the enforcing
`u:r:hibreak_display:s0` domain in the default release. The base compatibility
image uses `u:r:phhsu_daemon:s0` instead. Running the earlier service as shell produced
`Parcel(Error: ... "Operation not permitted")` even with exit status 0.
The helper logs its selected method, accepts whitespace in Parcel replies,
and verifies `h/w composer disabled` in SurfaceFlinger's dump before reporting
success. It retries for 30 seconds and logs failures, including unavailable
services, rejected transactions and unconfirmed composition state.
Do not interpret a successful shell exit alone as a successful Binder call.

The enforcing migration launches all five display/AOD helpers through
`/system/bin/sh`. Their scripts retain the `system_file` label, which is not
an allowed `entrypoint` for `hibreak_display`; the shell's `shell_exec` label
is allowed. Direct script entrypoints were observed to fail with enforcing
SELinux, preventing the disable-HW-overlays, wake-cycle and AOD helpers from
starting. No broader entrypoint permission is needed.

With the disable-HW-overlays helper blocked, switching from Boosted
(saturation 1.1) to Natural (1.0, identity matrix) was observed to switch
from client/GPU to vendor device composition and freeze physical updates.
Restoring Boosted recovered the panel without restarting Android or
SurfaceFlinger. This is a recovery workaround, not a replacement for forcing
client composition. After rebuilding and flashing the corrected image,
verify `h/w composer disabled` in `adb shell dumpsys SurfaceFlinger` and test
both color modes, sleep/wake and AOD on the physical panel. The correction
must remain effective after boot and any separately required SF restart.
The shell-entrypoint correction alone did not establish forced composition
on the subsequently flashed image. EvoX also deliberately grays out its
Developer Options overlay switch. A direct AIDL request did set `h/w composer
disabled`; Natural then retained client composition and physical updates
were confirmed working. This live test did not require an SF restart or
broader SELinux permissions.
The new dump-based verification additionally needs SurfaceFlinger to use
and write the helper's output pipe. The migration grants only that `fd use`
and `fifo_file write` access; the previously flashed policy lacked both.

A captured reboot then showed the helper verifying `h/w composer disabled`
before TrebleApp started, yet HWC was enabled afterwards. Root cause:
TrebleApp (system UID) replays its **Disable HW overlays** preference
(`key_display_no_hwcomposer`, default off) on startup, about 20 seconds
after `sys.boot_completed`. With the switch off, it sends
`SurfaceFlinger 1008` with 0, re-enabling device composition. Enable that
switch in Treble Settings so TrebleApp forces GPU composition itself at
every boot. As a fallback for fresh installs, the wake helper also checks
SurfaceFlinger every 5 seconds for 180 seconds after boot and reapplies if
HWC was re-enabled. A later TrebleApp restart outside that window still
depends on the switch.

Setting properties before startup avoids restarting SF at boot. Runtime
restarts can desynchronize panel power and should be recovery operations only:

```bash
adb shell setprop debug.hibreak.disable_hwc 1
# Only if necessary:
adb shell setprop debug.hibreak.restart_sf 1
```

Screenshots/scrcpy are useful but not proof of physical panel correctness;
some overlay/shim combinations showed a correct virtual image and a broken
panel, or a black screenshot while the physical panel still updated.
