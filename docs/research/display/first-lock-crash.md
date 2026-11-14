# First-lock composer crash investigation (2026-10-27)

The user reports needing to unlock once and lock again after each reboot,
followed by an apparent UI restart before the display and Eink Settings popup work.
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
  SurfaceFlinger reported `h/w composer disabled`, and Eink Accessibility Service was
  enabled and bound with no service listed as crashed. These are
  **post-recovery** observations, not proof of correct first-boot state.
- `doze_always_on=0`, AOD inversion preference was false, and inversion was off.
  The AOD setup marker was already 1. This was not a fresh-install run enabling
  AOD for the first time.

There is no captured first-unlock/lock event sequence proving which interaction
triggers the crash, nor a snapshot of the unresponsive state before recovery.
The popup failure could accompany loss of display/framework services, but a
separate early Eink Settings initialization failure has not been excluded.

Next: capture continuously from a cold boot through first unlock and lock,
with helper lifecycle and SurfaceFlinger state timestamps. Then compare a
build without the automatic post-boot wake helper, keeping the early display
properties and SurfaceFlinger-start overlay fix unchanged. Test Eink Settings startup
separately if necessary; do not remove all display fixes together or add an
automatic SurfaceFlinger restart as a speculative workaround.

Evidence is retained locally in `build/boot-investigation-20261027/`, including
the crash buffer, full log snapshot, installed rc/scripts, Dropbox records,
and display/accessibility dumps. No reboot, settings change, flash, or
service restart was performed for this collection.

## Continuous first-unlock capture (2026-10-27, 13:09 EDT)

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
| 13:09:33.799 | Eink Accessibility Service logs service connection and applies its settings after recovery. |

The crash buffer again shows `processImage+1308`, `x1=-1` and comparison length
`0x52e200`. This capture ties the crash much more closely to the **first
power-button sleep transition after unlock**, rather than to unlocking itself.
The user timestamp and framework unlock logs differ by about three seconds;
both precede the sleep request and crash.

The overlay workaround was accepted before unlock, and the automatic wake
helper completed about eight seconds before the crash. This rules out the
simple explanation that the overlay workaround never ran, and weakens the
idea of a crash simultaneous with the helper. It does not exclude a display
state left behind by that helper. No pre-crash accessibility-service settings-application
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

## ColorFade lead (2026-10-27)

The LineageOS 23.2 GSI for the HiBreak Pro Color
([dianqk/LineageOS_gsi_HBPC](https://github.com/dianqk/LineageOS_gsi_HBPC/blob/lineage-23.2/hbpc/EINK-DISPLAY.md))
sets `config_displayColorFadeDisabled=true`. With ColorFade, screen-off takes
a full-screen screenshot and composites it under a fading cover layer. Our
image leaves it enabled (`dumpsys display`: `mColorFadeEnabled=true`).

The first-lock timeline fits: Power sleep at 13:09:23.096, display
`state=ON policy=OFF` at 23.113 (ColorFade off animation, 400 ms), `Blocking
screen off` at 23.532, composer crash at 23.538 comparing one full-screen
RGBA buffer. Not proven yet; this is a hypothesis.

Test image `build/HiBreakPro-no-colorfade.img` is the flashed
`HiBreakPro-wake-restored.img` plus one static RRO,
`system/product/overlay/HiBreakNoColorFade.apk` (package
`me.hibreak.overlay.nocolorfade`, target `android`, priority 90), built with
apktool from `build/colorfade-rro/src/`. After flashing, check
`dumpsys display | grep mColorFadeEnabled` (expect `false`), then reboot,
unlock and press Power.

Result (13:47): **ColorFade ruled out.** After flashing, `mColorFadeEnabled=false`
and the overlay was listed as enabled, but the first lock after unlock
still crashed at 13:47:17.233 with the same `processImage+1308` signature.

## Locked first-sleep test (2026-10-27, 13:50)

TrebleDroid's staging patch 0006 ("fix display power-on for vendor HWCs with
stale bootloader state") suggested that the first composer power-off after
boot might be the trigger. Test on the no-ColorFade image: reboot, keep the
phone locked, let it power the display off. The keyguard timeout turned it
off at 13:50:59 and 13:51:33 (composer logged `ion_fb_event: screen-off`), and
an ADB sleep/wake followed. **No crash.** The first power-off after boot is not
sufficient; the stale-power-state hypothesis is rejected for this symptom.

The user then unlocked (13:52:03; framework `BOOT_COMPLETED` broadcast at
13:52:04.165), used the launcher, and locked (~13:52:13; screen-off without a
crash). The crash came at **13:52:35.956, 130 ms after the next wake**
(`debug.tracing.screen_state=2` at 13:52:35.824). So the trigger is a display
power transition after the first unlock, sometimes sleep and sometimes wake,
not specifically sleep. `processImage: convertToGray` runs while locked too, so
the path itself is not unlock-gated.

Logging gaps: the logcat ring buffers were only 256 KiB, so the main/system
lines before each crash were overwritten by kernel `tee-log` spam, and the
streaming capture ended at 13:52:04, right after unlock (likely USB
re-enumeration). `adb logcat -G 16M` works at runtime but does not persist;
set Developer options → Logger buffer sizes → 16M for later captures and use
a reconnecting capture loop.

Evidence: `build/no-colorfade-crash-20261027/`, `build/locked-first-sleep-20261027/`.
