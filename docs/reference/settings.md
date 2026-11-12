# E-Ink settings

This page describes the user-visible controls in the patched E-Ink app.
Implementation details and limitations are in
[app and daemon](app-and-daemon.md), and stock mode values are in
[refresh-mode research](refresh-modes.md).

## Button mappings

The default single press of the E-Ink button refreshes the screen; a double
press opens the E-Ink menu with per-app refresh modes. These mappings can be
changed in E-Ink Settings. Button mappings are shown **top button first, then
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

The Shortcuts tab supports:

- **Configure shortcut**: apps exposing Android's `ACTION_CREATE_SHORTCUT`
  configuration flow. Choose an app, configure its shortcut, and confirm.
  Cancelling configuration keeps the previous assignment.
  Intent-based shortcuts with primitive/string extras are supported; shortcuts
  relying on temporary clip data or complex extras are rejected with an
  explanation rather than saved with missing data.
- **Launcher shortcut**: enabled static, dynamic and pinned shortcuts exposed
  through `LauncherApps`, when this app has Android shortcut-host permission.
  Selected shortcuts are pinned for this app to retain dynamic shortcuts.
  Android normally reserves this access for the default launcher or a
  system-authorized shortcut host. The picker explains unavailable access;
  it does not replace your launcher or grant itself privileges.

Only apps and shortcuts in the current Android profile are shown. Apps must
expose a supported shortcut; arbitrary internal app screens cannot be listed.
Removed/disabled shortcuts and revoked permissions can still prevent launches;
failures are reported rather than silently opening the app's home screen.

App and shortcut actions assigned with the screen off wake the display before
launching. They do **not** unlock the phone or bypass the keyguard. Android or
the target app may require unlocking before its content becomes available.

API/design references:
[Android launcher shortcut access](https://developer.android.com/reference/android/content/pm/LauncherApps),
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
sets `sys.linevibrator_touch`, not the frontlight driver or slider limits. Use
the popup's independent cold/warm frontlight sliders (0–255).

**E-Ink Service Settings → Invert colours on Always-On Display** is on by
default. It controls whether `hibreak-aod.sh` inverts colours while dozing.
The setting is re-sent whenever the accessibility service connects. Configure
the actual AOD in Android's lockscreen settings; inversion is a separate
workaround. The legacy static-lockscreen icon, opacity, background and colour
controls, including the popup opacity row, are removed or hidden on HiBreak.
They use an unsupported bitmap path, not Android SystemUI AOD. See the
[AOD reference](aod.md) for implementation details.
