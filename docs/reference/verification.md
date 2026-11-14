# Post-install verification

## HiBreak action and overlay update

On 2026-11-11, the user reported that the updated overlay, screen-off actions,
and app/shortcut assignments work on the HiBreak. ADB subsequently confirmed
that the active system APK at
`/system/priv-app/EinkSettings/HiBreakEink.apk` matches the supplied release APK
byte-for-byte. This is a successful user-reported device check, not an
independent exhaustive test of every gesture, shortcut provider, permission
state, or lock-screen condition; use the remaining checks below for broader
release validation. The subsequent removal of modern launcher shortcuts
requires a fresh device check.

Press Power right after the Bigme logo flashes, wait for boot, open Eink Settings and enable Eink Accessibility Service and
draw-over-other-apps permission. Top/bottom customization buttons have separate
single/double/long-press mappings, including screen-off mappings.
With the accessibility service enabled, fingerprint-sensor F9 events are consumed
without running a custom-button action. Verify that touching the power button
does not send F9 to the focused app, while pressing Power still locks/wakes the
phone and fingerprint unlocking still works. Other F9 input is also consumed.
Settings and the floating menu use standard Material 3 widgets and system
dynamic colors in light/dark mode. Check text contrast, selected refresh-mode
highlighting, all three switches, frontlight sliders, dialogs, and back
navigation on the physical e-ink panel after updating the source-built APK.
Rotate with the popup open and closed, with gesture navigation and three-button
navigation. It should stay inside system bars/cutouts, remain centred and no wider
than 640 dp, and scroll to all controls in landscape without resetting their values.
Rotate again while a settings choice dialog is open; its selection should survive,
and Back/cancel must leave the saved value unchanged.
With **Force accent color** off, confirm the shade and scheme controls are
disabled and service startup does not replace Android's current palette.
Enable it and try all five gray presets, including black and white. Select
**Custom gray**: its thin Material slider should appear with a black-to-white
gradient, no tick marks/end stops, and a live hex readout. Touch drags should
apply on release; accessibility changes should apply immediately. Rotate after
saving and check that the custom shade and preset are retained. Switching the
override off must leave the current Android palette in place, not restore or
apply a different one; re-enabling it should apply the saved shade.
At the temperature slider's centre the label should be 50%, not a neutral-white label.
With **Use Android brightness for frontlight** on (the default), check that the system
slider, auto-brightness and an app brightness override (e.g. a reader) change
the frontlight, that the popup shows combined brightness and temperature sliders, that it
snaps to the neutral-white stop, that moving
it keeps brightness steady at medium brightness, and that turning the switch
off restores the previous cold/warm values. `adb logcat -s DisplayBrightness`
reports if the app fell back to the slider-only setting.
Drag the popup brightness slider and check that output changes before release,
Android's saved brightness updates, and auto-brightness remains in its previous
mode (test both enabled and disabled). While dragging, delayed Android brightness
events must not move the thumb or override the live output. Later auto-brightness
adjustments should still take effect. Check the independent cold/warm sliders for
approximately even perceived brightness steps, including off and full output.
After releasing the popup brightness slider, wait for Android display events
and reopen the popup: it must not return to the previous brightness. Compare
`adb shell settings get system screen_brightness` with the display service's
cached brightness; the obsolete `screen_brightness_float` setting is not authoritative.
For manual brightness without dimming or an app override, the expected linear
value is approximately `(screen_brightness - 1) / 254`, clamped to 0–1.
The popup percentage uses perceptual CIE L* spacing, so it is not the saved
integer divided by 255. Inspect the authoritative values with:

```bash
adb shell settings get system screen_brightness_mode
adb shell settings get system screen_brightness
adb shell dumpsys display | grep -E 'mCachedBrightnessInfo\.(adjustedBrightness|brightness)='
```

Repeat with auto-brightness enabled: its mode must remain enabled, but later
automatic changes may legitimately move the slider. Test a rapid drag followed
by release without moving the thumb again, then change temperature and rotate
or reopen the popup. The released brightness must not revert merely because
a stale display event arrived during the drag. Allow for integer rounding.

The Apps and Shortcuts picker supports search and preserves the current
assignment when cancelled. Only app-provided shortcut configuration is
supported; modern launcher shortcuts are not listed or launched.
Screen-off app/shortcut launches wake the display without bypassing the
lock screen. Screen-off Clear Screen is removed, with existing assignments
migrated to Nothing. The overlay's top-right X closes it.
On Android 16, noninteractive keys may be dropped before reaching accessibility.
The root daemon therefore monitors the HiBreak's `mtk-kpd` side-key events without
grabbing the input device and forwards them to a receiver restricted to senders
with `INJECT_EVENTS`. The app accepts the bridge only for gestures starting with
the screen off; normal accessibility input continues to handle screen-on gestures.
Both the updated APK **and daemon** are required, so install this fix with an image
update, not just an APK update. Launching an app wakes the display but does not
bypass a secure lock screen.

```bash
adb devices
adb shell getprop sys.boot_completed
adb shell getprop debug.sf.enable_gl_backpressure
adb shell getprop debug.sf.enable_hwc_backpressure
adb shell dumpsys SurfaceFlinger | grep 'h/w composer disabled'
adb logcat -d -s hibreak-display a9EinkService
tools/device/collect-diagnostics.sh build/diagnostics-after-boot
```

Expect boot completion `1`, both backpressure properties `false`, and disabled
HWC. Init oneshot services normally show `stopped` **after successful completion**;
inspect logs, not that state alone. A running daemon also does not prove that
the app can send commands or that the panel responds.

Eink Settings is a persistent system app: `adb install` fails with
"persistent app, not updateable". Update it by building and flashing a new image.

If the popup still shows the old order after flashing, check the active APK:

```bash
adb shell pm path com.lmqr.ha9_comp_service
```

A `/data/app/` path means an older installed update overrides the system copy.
After confirming the new image contains the corrected app, remove only that
package's update (this may reset app preferences):

```bash
adb shell cmd package uninstall-system-updates com.lmqr.ha9_comp_service
adb shell pm path com.lmqr.ha9_comp_service
```

The path should now be `/system/priv-app/EinkSettings/HiBreakEink.apk`.
Check accessibility and overlay permissions again. The popup order is
**HD, Regal, Fast, Extreme, Hyper**.

Do not assume a successful package install proves mode speed or AOD appearance.
Test a selected mode, lock/unlock, and inspect the physical panel. See
[Findings](../research/README.md) for unsupported controls and the boot power-button issue.

## XRZ v2 overlay

If the image includes XRZ v2, follow its
[label and log checks](../build/xrz-overlay.md). Confirm SELinux remains
enforcing and check all four exact property labels. Do not interpret blank
shell `getprop` values as missing properties: the shell lacks read access on
the inspected build.

The [first v2 device snapshot](../research/display/xrz-graphics-policy.md#first-on-device-v2-check-2026-11-04)
confirmed the labels and loaded composer permissions, with no retained
composer crash or framework restart. It did not establish successful property
writes or stability across repeated sleep/wake and scrolling tests.

## Migration verification status

The default release builder includes the init e-ink bridge and enforcing
migrations for the HiBreak daemon and display/AOD helpers. Device checks and
reported results are summarized in the
[build and device-verification guidance](../build/build-image.md#init-bridge-and-enforcing-migrations).

The user reported that the migration test images and all features work. These
reports were not accompanied by a complete log set or regression matrix, so
they are useful device evidence, not independent confirmation of every
hardware path. The tested defaults are limited to the documented GSI/vendor
image pair. Upstream PHH services remain outside the migrations, and the PHH
root domain remains permissive; neither the policy reduction nor the enforcing
migrations are a claim that the full upstream policy is hardened or free of
existing neverallow diagnostics.
