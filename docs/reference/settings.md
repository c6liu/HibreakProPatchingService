# Eink Settings

This page describes the user-visible controls in Eink Settings.
Implementation details and limitations are in
[app and daemon](app-and-daemon.md), and stock mode values are in
[refresh-mode research](refresh-modes.md).

## Layout and appearance

The floating menu uses Material 3 controls, stays within system-bar and display
cutout insets, and is capped at 640 dp wide. It resizes when the screen rotates
and scrolls when the available height is short, without resetting control values.
Settings choice dialogs use Material styling and retain their selected choice
through rotation; cancelling does not change the setting.

**Color Scheme → Force accent color** is off by default. While off, the app
does not write Android's accent or palette, including when its service starts.
Turning it off leaves the current palette in place; it does not restore an
earlier Android palette. The scheme and shade controls are disabled while off.

Turn it on to apply the selected **Color Scheme Type** and **Accent color
preset**. Five presets are available: black (`#000000`), dark gray (`#404040`),
medium gray (`#808080`, the default), light gray (`#BFBFBF`), and white
(`#FFFFFF`). These are palette seed colors; Android generates the resulting
UI colors, which need not match the seed exactly.

Select **Custom gray** to show a compact Material 3 slider with a black-to-white
gradient behind its track and a live hex readout. It retains a 48 dp minimum
touch target and has no tick marks or stops. Touch drags apply on release,
rounding to an integer channel value from 0 to 255; keyboard and accessibility
changes apply immediately. The custom shade and preset choice survive rotation
and toggling the override off/on. Old accent-slider values remain stored but
are no longer used; enabling the override uses the new preset or custom shade.

## Button mappings

The default single press of the E-Ink button refreshes the screen; a double
press opens the E-Ink menu with per-app refresh modes. These mappings can be
changed in Eink Settings. Button mappings are shown **top button first, then
bottom button**. Available screen-on actions include **Up, Down, Left, and
Right**, which send Android DPAD key presses to the focused app. Screen-off
actions include media, **Launch App**, **Launch Shortcut**, and Nothing.
Clear Screen is available only with the screen on. Existing screen-off
Clear Screen assignments are migrated to Nothing; new installs also default
to Nothing with the screen off. Actions can be assigned to single, double
or long presses of either button. Whether a DPAD key
scrolls or changes focus depends on the foreground app.

### Apps and shortcuts

Select **Launch App** or **Launch Shortcut** to open the Material 3 target
picker. Its **Apps** and **Shortcuts** tabs include icons, labels, package
names and search. Choosing a target saves it for that specific gesture;
Back cancels without changing the existing assignment. Tap **App to launch**
or **Shortcut to launch** beneath an assigned action to change its target.
Existing app-launch assignments remain compatible.

The Shortcuts tab lists apps exposing Android's `ACTION_CREATE_SHORTCUT`
configuration flow. Choose an app, configure its shortcut, and confirm.
Cancelling configuration keeps the previous assignment. Intent-based
shortcuts with primitive/string extras are supported; shortcuts relying on
temporary clip data or complex extras are rejected with an explanation rather
than saved with missing data. Modern launcher shortcuts are not supported,
regardless of shortcut-host access. A previously saved launcher shortcut is
marked unavailable and must be replaced with an app-provided shortcut.

Only apps and shortcuts in the current Android profile are shown. Apps must
expose a supported shortcut; arbitrary internal app screens cannot be listed.
Removed apps or changed permissions can still prevent launches;
failures are reported rather than silently opening the app's home screen.

App and shortcut actions assigned with the screen off wake the display before
launching. They do **not** unlock the phone or bypass the keyguard. Android or
the target app may require unlocking before its content becomes available.

API/design references:
[shortcut creation intents](https://developer.android.com/reference/android/content/Intent#ACTION_CREATE_SHORTCUT),
and [Material 3 app bars](https://m3.material.io/components/app-bars/guidelines).

## Refresh modes

The popup and default-mode preference offer the same five modes:

| Mode | Driver value | Daemon command | Saved preference value |
|------|--------------|---------------|------------------------|
| HD | 2147483825 (`0x800000b1`, HD_256) | `s` | 2 |
| Regal | 180 | `c` | 0 |
| Fast | 178 | `b` | 1 |
| Extreme | 179 | `p` | 3 |
| Hyper | 183 | `h` | 4 |

The selector and popup use this order. Existing saved values and per-app
choices retain their meanings. Hyper needs the matching updated daemon and is
exposed by the stock 3.1.6 framework; it is not guaranteed to increase refresh
speed on every GSI. The more detailed stock mapping, including the HD_256
driver value, is in [refresh-mode research](refresh-modes.md).

Open the separate **Per-App Refresh Modes** page to choose a mode for each
installed launcher app. **Use default** removes an app's override. Modes apply
when switching apps while the accessibility service is enabled.
**Disable Per-App Refresh Mode** temporarily uses a shared mode without
deleting saved choices. **Default Refresh Mode** remains editable while
per-app modes are enabled and is used for apps without an override.

**Reset all to default** asks for confirmation, then removes saved per-app
refresh-mode overrides, including those for uninstalled apps. It does not
reset the Additional Controls, Default Refresh Mode, shared mode, or other
settings.

## Popup controls

Use the **X** button in the top-right corner to close the popup. The action
button toggle and outside-tap dismissal remain available.

The popup's **Auto Refresh**, **Anti-Shake**, and **Video refresh
(experimental)** switches are saved separately for each app and applied
automatically when switching apps. Open the popup while the intended app is
active to change its controls. This is independent of **Disable Per-App
Refresh Mode**, which only affects the five-mode selector. Apps without saved
choices inherit the previous global Auto Refresh and Anti-Shake settings;
Video Refresh defaults off. The switches are disabled until an active app is
detected.

Enable **Video refresh (experimental)** for video apps to keep a tiny overlay
changing every 50 ms while those apps are active, prompting the E-Ink
compositor to commit frames. It pauses when the screen is off, when switching
to an app without Video Refresh enabled, and when switched off. The separate
camera-preview keep-alive works independently. Continuous refresh may
increase battery use and ghosting; effectiveness depends on the player and
display path.

**Toggle Night Light** and **Toggle Backlight** have been removed from button
actions. They changed Android LCD color-temperature and screen-brightness
settings, not the HiBreak E-Ink display or its cold/warm frontlight.

**Color Scheme** changes Android's system palette and compatible apps' dynamic
colours, not the panel waveform or refresh mode. On the monochrome HiBreak,
colours appear as greys. `SPRITZ` is the muted/near-monochrome style.

**Allow Control via Broadcasts** enables the refresh-mode receiver while the
accessibility service is running. Automation can send
`EINK_REFRESH_SPEED_SMOOTH` (HD), `EINK_REFRESH_SPEED_CLEAR` (Regal),
`EINK_REFRESH_SPEED_BALANCED` (Fast), `EINK_REFRESH_SPEED_FAST` (Extreme), or
`EINK_REFRESH_SPEED_HYPER`. The old action names are kept for compatibility.
The separate `EINK_FORCE_CLEAR` native bitmap-clear action is unsupported on
HiBreak; use the app's Clear Screen action instead.

## Frontlight and AOD

**Override Max Brightness** is removed on HiBreak: its legacy command only
sets `sys.linevibrator_touch`, not the frontlight driver or slider limits. With
native control off, the popup's independent cold/warm sliders use the same
exponential brightness curve as native control. Travel is spread evenly across
the driver's codes (about 2.55 codes, roughly 7.4% more light, per 1% of travel).
Every code from 1 to 255 is reachable; zero is off. The bottom tenth covers
about 26 codes instead of the 94 that pure CIE L* would cover.
Saved channel codes are retained within the same app package, so changing
control modes does not reset independent brightness levels. The
[package-identity migration](../install/update.md#one-time-app-and-daemon-identity-migration)
requires fresh app configuration.

**Eink Accessibility Service → Use Android brightness for frontlight** (on by
default) switches to native control. Android's effective brightness — the
system slider, automatic brightness, screen dimming and per-app window
overrides — then sets the combined frontlight output, and the popup shows a
combined brightness slider and a cool-to-warm slider instead of the two
channel sliders. The saved independent values are kept and restored when
the switch is turned off. There is no explanatory hint row beneath the sliders.
The cool-light slider and cool end of the temperature slider use Material
Symbols **mode_cool**; the warm-light slider and warm end use **sunny**.

- Combined output is capped at 90% of both channels at full code.
- Changing the colour temperature keeps the combined output constant wherever
  both channels can supply it. Near pure cool or pure warm at high brightness
  one channel saturates; the light then dims instead of shifting colour.
- The slider keeps the full 8000–3000 K range, but neutral white (4800 K)
  sits exactly at the centre. Each half is evenly spaced in CIE 1976 u'v':
  colour changes about 0.82× as fast as the old uniform spacing on the cool
  half and 1.18× on the warm half (about 1:1.45). The two rates blend
  smoothly between 40% and 60% of the slider, so there is no kink.
- The slider snaps to the neutral-white centre within ±3%. Both channels use
  equal driver codes there, giving the most available combined output. It is
  also the default position. All slider labels remain percentages, including
  50% at neutral white; the centre snap and haptic feedback are retained.
- Android stores 255 integer brightness levels. They use the same exponential
  curve as the overlay, across the full range, without the previous 40%/60%
  joins. Each non-off Android step increases target light by about 2.8%.
  The lowest non-off setting reaches LED code 1 at neutral white; the lowest
  setting remains off. The cap and mixing can repeat or skip codes, so native
  mode does not promise all 256 codes at every temperature. This mapping also
  applies to automatic brightness and app overrides. Existing Android values
  are retained, but intermediate light levels are dimmer than with the old curves.
- Mixing is done in linear light and converted through the LM3630A's
  exponential code curve (`0.85^(44 − (code + 1) / 5.8181818)`).
- On the tested GSI, Android reports the system slider's brightness change
  on release rather than continuously while dragging.
  The popup brightness slider instead updates the lights live and saves Android's
  supported integer brightness setting (rounded to its 1–255 range).
  Releasing the popup slider saves its final requested value again before
  resuming Android tracking, so a delayed value received during the drag does
  not become the released position. Small rounding changes are possible.
  It never changes the auto-brightness mode; subsequent automatic adjustments
  or app brightness overrides can take over.
- All popup sliders use Material 3 controls. The combined brightness slider
  directly represents normalized Android brightness; no second curve is applied.
  The same popup position gives the same target share of each mode's maximum,
  before native mixing, the cap and rounding. The image sets
  `sys.brightness.disable_gamma_conversion=true`, using the tested EvoX System UI's
  built-in switch to disable its additional perceptual conversion. With the
  tested 0-1 display brightness limits, the native system slider then follows
  the overlay's positions and response, allowing for integer rounding. The
  overlay curve is unchanged. Other GSIs must support this property; setting it
  alone cannot change a System UI that ignores it. The unavoidable off-to-minimum
  hardware step remains. Temperature retains its centred neutral-white stop.

Calibration in `FrontlightMixer.kt` comes from panel measurements: cool alone
8000 K, warm alone 3000 K, both at full 4800 K. That implies the warm channel's
full output is about 0.82 of the cool channel's. At full brightness the slider
centre reaches the full cap; the cool end gives about 61% and the warm end 50%.

**Eink Accessibility Service → Invert colours on Always-On Display** is on by
default. It controls whether `hibreak-aod.sh` inverts colours while dozing.
The setting is re-sent whenever the accessibility service connects. Configure
the actual AOD in Android's lockscreen settings; inversion is a separate
workaround. The legacy static-lockscreen icon, opacity, background and colour
controls, including the popup opacity row, are removed or hidden on HiBreak.
They use an unsupported bitmap path, not Android SystemUI AOD. See the
[AOD reference](aod.md) for implementation details.
