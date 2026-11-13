# E-Ink app and daemon

What the patched E-Ink app and native daemon contain. Build them with
[Build a release image](../build/build-image.md); user-visible settings are
summarized in the [settings reference](settings.md).

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
The default refresh mode for new apps is Fast. Existing saved global and
per-app choices are preserved. Changing apps applies the new app's controls and updates popup switches
without saving the previous app's values into the new app. Controls remain
disabled until an active app is detected. The per-app page's reset action resets
refresh modes only, not these controls. The camera-preview keep-alive remains
independent of the per-app Video Refresh choice.
It has `sharedUserId` removed so it can run without the GSI's platform signing
key. The AOSP module keeps its platform-signed integration configuration.

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
  and writes `screen_brightness_float` through `WRITE_SETTINGS`, without changing
  automatic/manual mode. It uses CIE L* perceptual spacing, as do the independent
  channel sliders; temperature retains the centred neutral-white stop.
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
  change HiBreak frontlight values or the 0–255 popup slider limits. This
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
