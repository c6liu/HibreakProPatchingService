# Post-install verification

Press Power right after the Bigme logo flashes, wait for boot, open E-Ink Settings and enable the accessibility service and
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
The "App to launch" row uses the same standard layout as the other settings,
and appears directly below its action only when "Launch App" is selected.
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
tools/collect-diagnostics.sh build/diagnostics-after-boot
```

Expect boot completion `1`, both backpressure properties `false`, and disabled
HWC. Init oneshot services normally show `stopped` **after successful completion**;
inspect logs, not that state alone. A running daemon also does not prove that
the app can send commands or that the panel responds.

The E-Ink app is a persistent system app: `adb install` fails with
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

The path should now be `/system/priv-app/HiBreakEink/HiBreakEink.apk`.
Check accessibility and overlay permissions again. The popup order is
**HD, Regal, Fast, Extreme, Hyper**.

Do not assume a successful package install proves mode speed or AOD appearance.
Test a selected mode, lock/unlock, and inspect the physical panel. See
[Findings](../research/README.md) for unsupported controls and the boot power-button issue.

## Optional XRZ v2 overlay

If the image includes XRZ v2, follow its
[label and log checks](../build/xrz-overlay.md). Confirm SELinux remains
enforcing and check all four exact property labels. Do not interpret blank
shell `getprop` values as missing properties: the shell lacks read access on
the inspected build.

The [first v2 device snapshot](../research/display/xrz-graphics-policy.md#first-on-device-v2-check-2026-11-04)
confirmed the labels and loaded composer permissions, with no retained
composer crash or framework restart. It did not establish successful property
writes or stability across repeated sleep/wake and scrolling tests.
