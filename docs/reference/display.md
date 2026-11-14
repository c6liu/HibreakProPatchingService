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

## Display: the working recipe

Keep the stock vendor. Set both persistent phh backpressure properties and
their `debug.sf` counterparts to `false` before SurfaceFlinger starts:

```text
persist.sys.phh.enable_sf_gl_backpressure
persist.sys.phh.enable_sf_hwc_backpressure
debug.sf.enable_gl_backpressure
debug.sf.enable_hwc_backpressure
```

Disable HW overlays using `service call SurfaceFlinger 1008 i32 1`. This is
the Developer Options setting, not a switch to disable the physical panel's
vendor HWC driver. SurfaceFlinger forgets it on restart, so init re-applies it.

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
The script inspects the Parcel reply, retries for 30 seconds and logs failure.
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
