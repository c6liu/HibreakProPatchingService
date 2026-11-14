# Eink Settings and daemon

What Eink Settings and its native daemon contain. Build them with
[Build a release image](../build/build-image.md); user-visible settings are
summarized in the [settings reference](settings.md).

The app is named **Eink Settings**, and its accessibility service is
**Eink Accessibility Service**. The package is `com.lmqr.eink_settings`,
with accessibility component `.EinkAccessibilityService`. This identity
change is a new app installation: settings and accessibility bindings from
the previous package do not carry over automatically.
Source lives in `eink_settings/`; the image installs the APK at
`/system/priv-app/EinkSettings/HiBreakEink.apk`.
Daemon source lives in `eink_daemon/`; its binary and init service are
`eink_server`, using the abstract socket `eink_socket`. Deploy the app and
daemon together so their socket and side-key broadcast identities match.

The APK gains five modes, the in-layout toolbar, the AOD inversion switch,
screen-on DPAD button actions, an opt-in video-refresh popup toggle, and per-app
refresh selectors on a separate page
for installed launcher apps, with a confirmed reset-all action. Button
settings appear top-first. Unsupported legacy static-lockscreen controls are
removed/hidden, as are the LCD-only Night Light and Backlight button actions.
The legacy max-brightness override is removed. Build the daemon from the
matching source so it can dispatch the new DPAD commands.
The popup's Auto Refresh, Anti-Shake, and Video Refresh controls are saved
per app, independently of the per-app refresh-mode enable/disable setting.
Auto Refresh and Anti-Shake default on when no global or app-specific value has
been saved; Video Refresh defaults off and the old global video flag is ignored.
The default refresh mode for new apps is Fast. Within the same app package,
existing saved global and per-app choices are preserved. Changing apps applies
the new app's controls and updates popup switches
without saving the previous app's values into the new app. Controls remain
disabled until an active app is detected. The per-app page's reset action resets
refresh modes only, not these controls. The camera-preview keep-alive remains
independent of the per-app Video Refresh choice.
It has `sharedUserId` removed so it can run without the GSI's platform signing
key. The AOSP module keeps its platform-signed integration configuration.
Manifest lint suppressions are scoped to the intentional protected-permission
requests: `WRITE_SECURE_SETTINGS` and `DUMP` are privileged-allowlisted;
`CONTROL_DISPLAY_BRIGHTNESS` is only grantable in the platform-signed build.

All builders refuse to overwrite existing outputs. Choose new filenames when
rebuilding. A failed image build can leave an incomplete output; do not flash it.

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
- Native frontlight mode reads Android's effective brightness
  (`BrightnessInfo.adjustedBrightness`). The hidden `getBrightnessInfo()` needs
  the signature-only `CONTROL_DISPLAY_BRIGHTNESS`, which the standalone-signed
  APK cannot hold, so the app instead parses the default display's
  `mCachedBrightnessInfo.adjustedBrightness` from the display service dump
  (privileged `DUMP`, allowlisted in `privapp-permissions-accessibility.xml`).
  Updates are triggered by the hidden brightness-only display event. If both
  reads fail, it falls back to the saved slider setting, which ignores
  auto-brightness and app overrides. This mode targets Android 16 and later.
  The popup's Material 3 combined-brightness slider applies the mix immediately
  and writes `Settings.System.SCREEN_BRIGHTNESS` through `WRITE_SETTINGS`, without
  changing automatic/manual mode. On the tested GSI, Android's brightness
  synchronizer maps setting 1–255 to linear output 0–1. The old
  `screen_brightness_float` key is not the display service's float brightness
  setting and is ignored: writing it left the effective brightness unchanged,
  so a later display read reset the slider and lights. Own setting notifications
  no longer trigger an early read of the stale display cache, and releasing a
  drag reaffirms its final value before returning to Android tracking.
  For requested Android brightness `b`, the write is
  `screen_brightness = round(clamp(b, 0, 1) * 254) + 1`; the setting fallback
  reads `clamp((screen_brightness - 1) / 254, 0, 1)`.
  Reads queued before a newer local write are discarded. During a drag, live
  output uses the thumb's requested brightness rather than delayed display
  events. Later genuine Android brightness changes still take effect.
  At boot completion and on screen-on, the app reapplies the physical channel
  codes even when Android brightness is unchanged and refreshes the effective
  brightness. This is intended to address a physical post-boot mismatch
  that was corrected by screen off/on while Android's saved brightness
  remained correct; the exact startup writer/timing was not isolated.
  The source change still needs physical post-flash verification. It does
  not write Android brightness or change automatic/manual mode.
  `FrontlightMixer.outputForAndroidBrightness` maps `b` to light. It is linear
  from 0.4 up and logarithmic below, so the 255 integer levels reach down to
  about LED code 8 in steps of at most ~7%. The combined and independent
  brightness sliders share `outputForSlider`, which is CIE L* from 60% of travel
  and spreads the dark range evenly across LED codes below that. Inverses
  (`androidBrightnessForOutput`, `sliderForOutput`) place the thumb when the popup
  reopens, so saved codes and Android values are reproduced exactly. Temperature retains the centred neutral-white stop with
  a percentage-only label. Material Symbols `mode_cool` and `sunny` identify
  the cool and warm channels and the temperature slider's endpoints.
- Auto Refresh and Anti-Shake use the init bridge by default to write
  `/sys/kernel/debug/eink_debug/clean_a2` and `anti_flicker` asynchronously.
  The compatibility daemon uses direct writes instead. Request success does
  not acknowledge the hardware write; init logs failed bridge actions.
- Native bitmap commit and native force-clear are not implemented for HiBreak.
  The app's separate Clear Screen action is the intended alternative.
- Threshold/contrast code still points at Qualcomm `epd_*` paths. These
  controls are not supported on the tested MediaTek device.
- Legacy static-lockscreen/sys.linevibrator preferences are not equivalent
  to Android SystemUI AOD. The icon/opacity/background/colour settings are
  removed and their popup controls are hidden: native bitmap commit is
  unsupported. The separate AOD inversion switch remains available.
- Max-brightness override only writes `sys.linevibrator_touch`; it does not
  change HiBreak frontlight values or the physical 0–255 channel-code limits. This
  unsupported legacy preference is removed. Color Scheme instead writes
  Android's `theme_customization_overlay_packages` secure setting to select
  a system palette/style; it is not an e-ink display mode. Writes are gated
  by `force_accent_color` (default false), including service startup and
  preference-change handling. `accent_color_preset` selects one of five
  grayscale seeds or `custom`; custom uses `accent_custom_gray` (0–255,
  default 128) as equal R/G/B channels. Turning the override off makes no
  palette write and does not restore an older palette. The old
  `color_scheme_color` value is not read or overwritten.
- Settings uses a no-action-bar theme plus an in-layout Toolbar and window
  insets. XML toolbar title/navigation plus a click listener avoid
  `setSupportActionBar`, which caused a `NoSuchMethodError` in an earlier
  R8-shrunk prebuilt. The overlay uses explicit AppCompat image widgets
  and `app:tint` so light/dark theme icon colors work with service-context
  inflation, without depending on an activity's inflater factory.
- The APK is standalone rather than using the platform shared UID.
  A matching signature is necessary for updates; `/data/app` updates can
  override system copies. Do not mistake a new system image for a guaranteed
  app update.
