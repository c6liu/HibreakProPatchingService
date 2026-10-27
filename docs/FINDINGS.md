# HiBreak Pro GSI investigation

Observed on one black-and-white HiBreak Pro during October 2026. Distinguish
working configurations from experiments; these notes do not establish support
for the HiBreak Pro Color or every vendor revision.

## Hardware and working baseline

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
checked-in init services run as **uid 0**, in existing
`u:r:phhsu_daemon:s0`. Running the earlier service as shell produced
`Parcel(Error: ... "Operation not permitted")` even with exit status 0.
The script inspects the Parcel reply, retries for 30 seconds and logs failure.
Do not interpret a successful shell exit alone as a successful Binder call.

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

## Observed graphics crash and soft restart

**Symptom (user report, 2026-10-26):** the UI broke and Android soft-restarted
once while scrolling or opening an app in **Extreme** mode.

**Evidence** (crash log buffer and dropbox, collected right after the report):

- `06:32:56.836` `SIGSEGV` (`SEGV_MAPERR`, fault addr `0xffffffffffffffff`) in
  the stock vendor `android.hardware.graphics.composer@2.3-service`,
  thread `Dispatcher_0`. Backtrace:

  ```text
  #00 libc.so              __memcmp_aarch64+16
  #01 hwcomposer.mt6877.so OverlayEngine::processImage(OverlayPortParam*, CommitInfo*)+1308
  #02 hwcomposer.mt6877.so OverlayEngine::preProcessFrame(sp<FrameInfo>)+312
  #03 hwcomposer.mt6877.so OverlayEngine::triggerEink(sp<FrameInfo>)+124
  #04 hwcomposer.mt6877.so OverlayEngine::trigger(...)
  #05 hwcomposer.mt6877.so HWCDispatcher::PhyPostHandler::process(DispatcherJob*)+916
  ```

  `hwcomposer.mt6877.so` BuildId `8a5cbea66efcb94a1a6cfdb53a239598`.
- `06:32:57.671` a new zygote logged `boot_progress_start` at kernel uptime
  153 s (the kernel had booted at about 06:30:35), and a new system_server
  followed. Dropbox recorded `SYSTEM_RESTART` at `06:33:10`. This is a
  framework (soft) restart caused by the composer dying, not a phone reboot.
- After the restart, `dumpsys SurfaceFlinger` again reports
  `h/w composer disabled`. No `hibreak-display` log lines were retained, so the
  logs do not show which trigger reapplied it.
- Dropbox holds six earlier tombstones with the **same** `processImage+1308`
  frame (04:38–04:40 EDT the same day, during display setup). So this is a
  recurring vendor composer crash, not a one-off.
- Another `SYSTEM_RESTART` at 06:14:39 has no matching tombstone. Its logs were
  no longer available, so its cause is unknown.

**Not related:** every boot logs a `SIGABRT` tombstone for `/system/bin/init
second_stage` with process uptime 0 s (`do_exec` → `Service::ExecStart`). That
is a forked `exec` child from a GSI/vendor rc file, not PID 1. This project's
rc files contain no `exec`. It happens at every boot and did not cause the
soft restart.

**Interpretation:** the crash is inside Bigme's closed E-Ink path of the stock
composer (`triggerEink` → `processImage`). Disabling HW overlays does not take
the vendor composer out of panel output and does not prevent it. The user's
report of Extreme mode during scrolling is context, not proof of the trigger;
the evidence does not establish the trigger, frequency, or whether refresh
mode or AOD changes contribute. This is unresolved; do not describe the
configuration as fully stable.

To capture the next occurrence before the logs rotate:

```bash
D=build/crash-$(date +%Y%m%d-%H%M); mkdir -p "$D"
adb logcat -d -b crash -v threadtime > "$D/logcat-crash.txt"
adb logcat -d -b all -v threadtime > "$D/logcat-all.txt"
adb shell dumpsys dropbox --print SYSTEM_TOMBSTONE > "$D/dropbox-tombstones.txt"
adb shell dumpsys dropbox --print SYSTEM_RESTART > "$D/dropbox-system-restart.txt"
```

Note the refresh mode and what you were doing. The evidence for the
2026-10-26 06:32 crash is kept locally in `build/crash-20261026-0632/`
(`build/` is not committed).

## Camera preview pauses

On 2026-10-26, the user reported intermittent multi-second freezes in the
live preview of Aperture (`org.lineageos.aperture`). Camera controls remain
responsive, and pressing an on-screen button immediately resumes the preview.
The user reproduced this in both **Fast** and **Hyper**; changing between
those modes is not a workaround.

During a separate five-second live sample, camera stream frames produced
advanced from 133 to 263. The preview uses a SurfaceView. These observations
show that frame production worked during that sample, not that it continued
during a confirmed freeze. The vendor composer also logged anti-flicker write
failures, but these are not established as the cause.

A redraw/presentation problem is a working hypothesis because UI interaction
resumes the preview. The cause remains unconfirmed; do not assume it is the
same failure as the composer crash above. No camera fix has been applied.
Logs and camera dumps are kept locally in `build/camera-20261026-0645/`.
The next diagnostic is to compare camera frame progression and SurfaceFlinger
preview timestamps during a confirmed pause, before touching any controls.

## Boot, sleep and the power-button report

**User-reported boot behavior:** after every restart or power-up, press the
Power button once right after the Bigme logo flashes. Otherwise, it may return to a
powered-off state. Treat this as a manual post-reboot step; this project does
not fix it.

A diagnostic reboot on 2026-10-26 without a physical Power press did not
reproduce that exact behavior: the device entered Android doze and remained
reachable over ADB. This observation does not invalidate the reported
power-button requirement.

Diagnostic details from that run:

- ADB returned about 12 seconds into boot.
- `sys.boot_completed=1` by about 33 seconds.
- Old boot helper sent `KEYCODE_SLEEP` at 05:56:31, then `KEYCODE_WAKEUP`
  two seconds later; the log records a successful wake.
- At 05:56:43 Android entered doze due to **timeout**, not a shutdown request.
- At 127 seconds uptime, ADB was still connected, boot complete was still 1,
  display state was 4 (`DOZE_SUSPEND`), and PowerManager reported `Dozing`.
- An ADB `KEYCODE_WAKEUP` later changed the state to `Awake`/display state 2
  and removed the AOD inversion marker. No physical button was needed.

Thus this observed instance was Android sleep/AOD, not a power-off. That does
not rule out a different intermittent PMIC, bootloader or kernel failure.
Retained boot reasons were `reboot` / `reboot,fastboot`; no Android shutdown
sequence was found for the observed interval.

The old helper forced a sleep cycle on **every** boot, based on a first-boot
workaround. The consolidated helper now only wakes by default. Its optional
legacy sleep/wake cycle is gated by root-set
`persist.sys.hibreak.boot_sleep_cycle=true`. This removes unnecessary boot-time
sleep, but **is not a verified fix for a genuine hardware power-off**. Normal
screen timeout and AOD remain enabled; this does not keep the screen awake
forever or change battery behavior.

To investigate a recurrence, connect USB and collect diagnostics before
holding Power. `adb get-state`, uptime, boot completion, `dumpsys power`, and
shutdown logs distinguish sleep from Android shutdown. If ADB disappears,
that alone does not prove power loss (USB/adbd may also fail); capture the next
boot reason and, with suitable authorized root, pstore/last-kmsg if available.
Pstore was not readable by the normal ADB shell on this build.

### First-unlock/lock freeze and soft restart (2026-10-27)

The user reports needing to unlock once and lock again after each reboot,
followed by an apparent UI restart before the display and A9 popup work.
Read-only collection from the connected device confirms a graphics crash on
the latest boot:

| Local time (EDT) | Evidence |
|-----------------|----------|
| 12:54:06.030 | First zygote `boot_progress_start`, kernel uptime 10.536 s. |
| 12:54:27.765 | A receiver in the phone process logs `ACTION_BOOT_COMPLETED`. |
| 12:54:32.256 | Vendor composer PID 1434, thread `Dispatcher_0`, takes SIGSEGV reading `0xffffffffffffffff`. |
| 12:54:32.407 | Crash backtrace reports `__memcmp_aarch64+16`, `OverlayEngine::processImage+1308`, `preProcessFrame`, then `triggerEink`. |
| 12:54:33.230 | New zygote `boot_progress_start`, kernel uptime 37.737 s. |
| 12:54:50 | Dropbox records `SYSTEM_RESTART`. |

This is the same vendor-composer crash signature as the earlier scrolling
failure, now confirmed during boot. The installed vendor composer init service
has `onrestart restart surfaceflinger`; SurfaceFlinger's service has
`onrestart restart --only-if-running zygote`. These rules explain why the
composer crash restarts the Android framework rather than only the panel.
Aurora Store also crashes immediately afterwards with display receiver error
`status=-32`; that is consistent with the display service disappearing, not
evidence that Aurora caused the composer crash.

The `memcmp` register arguments include an invalid second buffer pointer
(`x1=-1`) and length `0x52e200` (824 x 1648 x 4 bytes, one full RGBA frame).
This establishes an invalid frame-sized buffer comparison in the vendor path.
It does not establish where that pointer originated or prove a failed `mmap`.
The normal ADB shell cannot read the vendor library on this device.

Relevant installed startup behavior:

- The display rc sets backpressure properties at `early-boot`, requests
  disable-HW-overlays when SurfaceFlinger starts, and starts the wake helper
  plus AOD setup at `sys.boot_completed=1`.
- The wake helper waits five seconds, reapplies disable-HW-overlays, sends
  `KEYCODE_WAKEUP`, and reapplies disable-HW-overlays a second time.
  `persist.sys.hibreak.boot_sleep_cycle` is unset on this device, so the
  helper's optional `KEYCODE_SLEEP` branch is **not enabled**.
- The observed crash is roughly 4.5 seconds after the retained boot-completed
  receiver log. This makes boot-helper timing worth testing, but that receiver
  log is not the exact init property transition or helper start time.
  No `hibreak-display` messages survived in the captured logs, so neither
  helper completion nor its ordering against the crash is established.
- At collection time, both backpressure properties were false,
  SurfaceFlinger reported `h/w composer disabled`, and A9 accessibility was
  enabled and bound with no service listed as crashed. These are
  **post-recovery** observations, not proof of correct first-boot state.
- `doze_always_on=0`, AOD inversion preference was false, and inversion was off.
  The AOD setup marker was already 1. This was not a fresh-install run enabling
  AOD for the first time.

There is no captured first-unlock/lock event sequence proving which interaction
triggers the crash, nor a snapshot of the unresponsive state before recovery.
The popup failure could accompany loss of display/framework services, but a
separate early A9 initialization failure has not been excluded.

Next: capture continuously from a cold boot through first unlock and lock,
with helper lifecycle and SurfaceFlinger state timestamps. Then compare a
build without the automatic post-boot wake helper, keeping the early display
properties and SurfaceFlinger-start overlay fix unchanged. Test A9 startup
separately if necessary; do not remove all display fixes together or add an
automatic SurfaceFlinger restart as a speculative workaround.

Evidence is retained locally in `build/boot-investigation-20261027/`, including
the crash buffer, full log snapshot, installed rc/scripts, Dropbox records,
and display/accessibility dumps. No reboot, settings change, flash, or
service restart was performed for this collection.

### Continuous first-unlock capture (2026-10-27, 13:09 EDT)

The user captured a reboot and supplied first-unlock timestamp `1793120953`
(13:09:13 EDT). The continuous log contains earlier boots and repeated buffer
replays after reconnects; duplicate crash lines are not additional crashes.
The relevant new boot has this sequence:

| Local time (EDT) | Evidence |
|-----------------|----------|
| 13:08:52.059 | First zygote starts at kernel uptime 10.572 s. |
| 13:08:53.253 | Disable-HW-overlays transaction accepted by SurfaceFlinger. |
| 13:09:09.247 | Another overlay-disable transaction accepted; AOD setup completes. |
| 13:09:13 | User's reported first-unlock timestamp. |
| 13:09:14.247 | Wake helper's overlay-disable transaction accepted. |
| 13:09:15.339–15.353 | Final overlay-disable transaction accepted; wake helper logs completion. |
| 13:09:15.903–15.926 | Keyguard logs `StartUnlock`; keystore logs `on_device_unlocked`. |
| 13:09:23.096 | PowerManager starts sleep explicitly due to `power_button`. |
| 13:09:23.538 | Vendor composer SIGSEGV, 442 ms after the sleep request. |
| 13:09:24.536 | Replacement zygote starts at kernel uptime 43.048 s. |
| 13:09:33.799 | A9 logs service connection and applies its settings after recovery. |

The crash buffer again shows `processImage+1308`, `x1=-1` and comparison length
`0x52e200`. This capture ties the crash much more closely to the **first
power-button sleep transition after unlock**, rather than to unlocking itself.
The user timestamp and framework unlock logs differ by about three seconds;
both precede the sleep request and crash.

The overlay workaround was accepted before unlock, and the automatic wake
helper completed about eight seconds before the crash. This rules out the
simple explanation that the overlay workaround never ran, and weakens the
idea of a crash simultaneous with the helper. It does not exclude a display
state left behind by that helper. No pre-crash `A9Service` settings-application
or daemon mode-application messages were found in the relevant captured boot
segment; absence of those messages does not prove that the service was unbound.

Next isolate first sleep from first unlock: compare a reboot where the phone
is left unlocked without pressing Power, then capture its first power-button
sleep transition. A wake-helper-free comparison remains useful if sleep is
the reproducible boundary. If the popup is already unavailable before sleep,
capture accessibility binding and app logs in that state, before recovery.
Do not change init's restart cascade to mask the vendor crash.

Evidence is local in `build/first-unlock-20261027-130809/`. Follow-up crash and
Dropbox records were collected read-only after the user's terminal commands
failed because `$D` was unset in that terminal. No repeat reboot was needed
to recover those records.

## Stock refresh control research

Examined the local stock backup's `framework.jar`, `xrz.framework.server.jar`,
xSettings and MediaTek SystemUI with apktool smali. Relevant classes:

- `xrz.framework.manager.XrzEinkManager`
- `EinkRefreshMode`
- `com.xrz.settings.einkcenter.RefreshModeDialog`, `EinkCenterDialog`,
  `AppRefreshSetDialog`, `EinkUiHelper`
- `DisplayPolicyController`, using `XrzEinkManagerInternal.setLayerRefreshMode`

Stock framework constants:

| Constant | Decimal | Hex |
|----------|---------|-----|
| CLEAN | 176 | 0xb0 |
| HD | 177 | 0xb1 |
| NORMAL | 178 | 0xb2 |
| FAST | 179 | 0xb3 |
| REGAL | 180 | 0xb4 |
| HYPER | 183 | 0xb7 |
| HD_256 | 2147483825 (unsigned) | 0x800000b1 |

The stock dialog lists **HD 256, Regal, Fast, Extreme, Hyper**. The patched app
uses the order **HD, Regal, Fast, Extreme, Hyper**:

| App label | Old label | Driver value | Command | Saved value |
|-----------|-----------|--------------|---------|-------------|
| Regal | Clear | 180 | `c` | 0 |
| Fast | Balanced | 178 | `b` | 1 |
| HD | Smooth | 2147483825 (`0x800000b1`, HD_256) | `s` | 2 |
| Extreme | Speed | 179 | `p` | 3 |
| Hyper | new | 183 | `h` | 4 |

The app label remains **HD**, but command `s` now requests the stock flagged
**HD_256** value rather than plain HD 177. The old preference indices and per-app
selections are preserved. Update the daemon in the image for this mapping to take
effect. Physical 256-level output on the GSI has not yet been verified.
Hyper is a stock-exposed mode, not a guaranteed speed boost.

The GSI daemon writes both
`/sys/kernel/debug/eink_debug/global_mode` and
`vendor.xrz.global_refresh_mode`. The stock `hwcomposer.mt6877.so` references
the vendor property. A normal shell cannot set all vendor properties; the
existing phh root domain can. To override for diagnosis without interactive su:

```bash
adb shell setprop debug.hibreak.refresh_mode 179
adb logcat -d -s a9EinkService
```

The accessibility service may overwrite that diagnostic value when switching
apps. Disable per-app modes while comparing speed. Auto-refresh (`clean_a2`)
and anti-flicker can also alter perceived speed/ghosting. No new waveform,
higher panel frequency or benchmarked speed guarantee is supplied.

Stock per-layer policy/native framework APIs are not fully reproduced by
global sysfs/property writes. The stock control-center APK depends on Bigme
framework services and is not a standalone app usable on arbitrary GSIs.
The backup remains the source of research evidence; proprietary stock APKs
and decompiled framework trees are not included in this repository.

## App controls, signing and known limitations

- Customization-button scan codes: **59 bottom**, **60 top**. Separate
  gesture detectors and mappings support single, double and long presses,
  including screen-off actions. Enable accessibility and overlay permission.
- Screen-on button actions can send Android DPAD up/down/left/right key events
  through the root daemon. The focused app decides whether those keys scroll,
  move focus, or do nothing. Legacy Night Light and Backlight actions modified
  Android LCD settings rather than the HiBreak frontlight, so they are removed.
- Frontlights use
  `/sys/devices/platform/11d01000.i2c7/i2c-7/7-0036/lm3630a_cold_light`
  and `lm3630a_warm_light` on the same path.
- Auto-refresh uses `/sys/kernel/debug/eink_debug/clean_a2`; anti-flicker uses
  `/sys/kernel/debug/eink_debug/anti_flicker`. Missing nodes are logged.
- Native bitmap commit and native force-clear are not implemented for HiBreak.
  The app's separate Clear Screen action is the intended alternative.
- Threshold/contrast code still points at Qualcomm `epd_*` paths. These
  controls are not supported on the tested MediaTek device.
- Legacy static-lockscreen/sys.linevibrator preferences are not equivalent
  to Android SystemUI AOD. The icon/opacity/background/colour settings are
  removed and their popup controls are hidden: native bitmap commit is
  unsupported. The separate AOD inversion switch remains available.
- Max-brightness override only writes `sys.linevibrator_touch`; it does not
  change HiBreak frontlight values or the 0–254 popup slider limits. This
  unsupported legacy preference is removed. Color Scheme instead writes
  Android's `theme_customization_overlay_packages` secure setting to select
  a system palette/style; it is not an e-ink display mode.
- Settings now uses a no-action-bar theme plus an in-layout Toolbar and window
  insets. The prebuilt APK is R8-shrunk: `setSupportActionBar` was missing,
  causing a `NoSuchMethodError`. XML toolbar title/navigation plus a click
  listener avoid that call. The resulting header was checked on-device.
- The APK is standalone rather than using the platform shared UID.
  A matching signature is necessary for updates; `/data/app` updates can
  override system copies. Do not mistake a new system image for a guaranteed
  app update.

## Always-On Display

Init forces `persist.sys.overlay.aod=true`; setup enables
`me.phh.treble.overlay.misc.aod_systemui`, then defaults `doze_always_on=1`
once. Subsequent user changes to Always-On Display are respected.

`hibreak-aod.sh` follows `debug.tracing.screen_state`: 3/4 are doze states,
2 is on. It turns Android accessibility color inversion on during doze, then
off on wake, using `persist.sys.hibreak.aod_inverted` to identify inversion it
owns. It leaves pre-existing user-enabled inversion alone and cleans up a
stale owned inversion marker during boot setup. This is a workaround through
global color inversion, not a new native AOD renderer.

**EInk Service Settings > Invert colours on Always-On Display** defaults on.
The app sends `aoi1`/`aoi0` to the root daemon, setting
`persist.sys.hibreak.aod_invert=true/false`. The daemon accepts only 0 or 1.
The preference is resent when the service connects. The next doze entry
applies the choice; normal wake removes any script-owned inversion.

The observed no-button reboot reached doze, enabled inversion, then removed
it after an ADB wake. Host build checks and app command tests cannot guarantee
the visual result for every theme, animation setting or third-party AOD.
The consolidated script exits nonzero and logs failed operations rather than
always returning success.

## What did not work / what not to repeat blindly

1. **HiBreak Pro Color HWC shim on this black-and-white device:** enlarged,
   cropped, banded output. Restoring stock vendor fixed geometry. The
   attempted passthrough switch did not disable its FD rewrite. Do not ship
   these experimental vendor images as the recommended solution.
2. **Blind HWC stride changes:** the RGBA pitch was consistent; successful
   EINK ioctl return codes did not establish correct panel output.
3. **EROFS GSIs:** the tested kernel lacks the required support; use ext4.
4. **Hisense A9 image patcher unchanged:** Qualcomm paths, model/density
   spoofing, framework modifications, and unverified policy changes do not
   form a safe HiBreak patch. Missing tools/labels also broke an attempted run.
5. **`adb root` as the fix:** hung or was unavailable on tested builds;
   `su 0` worked only on the separate SU diagnostic build. Root init helpers
   solved the rootless EvoX case.
6. **Wiping from fastbootd:** did not find userdata/metadata in this setup;
   an intentional factory reset worked from bootloader fastboot. Never wipe
   as part of an ordinary same-ROM patched-image update.
7. **Using mtkclient to flash `system_a`:** it is a dynamic logical partition
   inside super, not a standalone GPT partition. Use fastbootd for this task.
8. **Assuming a stock fallback slot protects data:** userdata is shared. Earlier
   slot A also had mismatched boot/dtbo after an incomplete OTA; this was a
   device-specific recovery issue, not a reason to copy boot images blindly.

## Reproducibility and script locations

The working display scripts now live under [tools/display](../tools/display).
[patch-gsi.sh](../tools/patch-gsi.sh) replaces the external display patcher and
the session-only image updater scripts. [build-apk.sh](../tools/build-apk.sh)
and [patch-apk.py](../tools/patch-apk.py) include the previously manual
standalone, five-mode, toolbar and AOD-switch edits. The NDK build has its own
checked-in wrapper. No session-state directory or hard-coded home is required.

Large binaries/tools are user-supplied inputs, not source-controlled payloads.
Local copies are in ignored `local/`; new builds and diagnostics are in
ignored `build/`. Original external copies are retained as historical backups,
not required by any current tool. Experimental third-party shim sources and
stock firmware backups are deliberately not copied into the supported path.

Validation: full APK decode/patch/rebuild/sign, strict NDK compile, synthetic
ext4 integration tests, and a complete original-EvoX-to-patched-image run.
The resulting image passed `e2fsck` and embedded-file verification.
The consolidated image and its wake-only default have **not been flashed**.

## References

- [vbbot's 20250507 release](https://github.com/vbbot/HibreakProPatchingService/releases/tag/20250507)
- [Original GSI notes](https://vbh.ai/hibreak-pro-gsi-release/)
- [Original Android 15 guide](https://vbh.ai/hibreak-pro-guide-4-flashing-the-android-15-gsi/)
- [EvoX Treble](https://github.com/Doze-off/EvoX_treble/releases)
- [HiBreak Pro XDA discussion](https://xdaforums.com/t/bigme-hibreak-pro-dimensity-900-mt6877-e-ink-phone.4723924/)
- [Pro Color shim research (not recommended for this baseline)](https://github.com/awong-dev/hibreak-pro-color)
