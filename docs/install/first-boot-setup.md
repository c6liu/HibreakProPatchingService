# First-boot setup

1. Complete Android setup.
2. Open **Eink Settings**, enable **Eink Accessibility Service** and allow
   **Display over other apps**.
3. Double-press the E-Ink button to open the refresh menu:
   **HD, Regal, Fast, Extreme, Hyper**. Use the **X** in the top-right to
   close the overlay.
4. Open **Treble Settings → Display settings** and enable
   **Disable HW overlays**. TrebleDroid replays this switch on every boot;
   while it is off, it re-enables vendor composition, which freezes panel
   updates (for example after selecting the Natural color mode).
5. Optional settings:
   - Choose separate single/double/long-press actions for the top and bottom
     buttons. Choose **Launch App** or **Launch Shortcut**, then select a
     target in the Apps or Shortcuts picker. Search to narrow the list; Back
     cancels without changing the assignment. Apps that provide
     `ACTION_CREATE_SHORTCUT` can configure a shortcut. Modern launcher
     shortcuts are not supported.
     Clear Screen is screen-on only; old screen-off Clear Screen assignments
     are changed to Nothing. Screen-off app and shortcut launches wake the
     display but do not unlock the phone or bypass the lock screen.
   - Configure refresh modes and display preferences as described in
     [Optional display tweaks](#optional-display-tweaks).
   - Set AOD inversion. Video refresh is experimental and opt-in per app.

USB debugging is not forced on by these release commands. Enable it in
Developer options when needed and authorize the PC on-screen. Updates
without a wipe preserve saved debugging settings and authorizations.
If upgrading from the previous app identity, repeat the app setup above:
its saved preferences and accessibility/overlay access do not carry over
automatically. See the [migration notes](update.md#one-time-app-and-daemon-identity-migration).

## Optional display tweaks

- Refresh modes are enabled **per application** by default. For one global
  refresh mode, enable **Disable Per-App Refresh Mode** in **Eink Settings**
  under **Eink Accessibility Service**.
- In **Phh Treble Settings** (shown as **Treble Settings** on the tested GSI):
  - Under **Mediatek settings**, enable **Mediatek GED KPI support**.
  - Under **Display settings**, enable **Disable SF GL backpressure** and
    **Disable SF HWC backpressure**.
  - Reboot after changing these settings. The patched image already disables
    both backpressure settings at boot; these toggles keep Treble Settings
    aligned with that configuration.
- In Android **Settings → Accessibility → Color contrast**, select **High**
  if you prefer higher-contrast interface colors. This is a UI preference,
  not a physical panel contrast or black/white-point adjustment.

These optional tweaks do not replace the required **Disable HW overlays**
setting above. See the [display reference](../reference/display.md) for the
composition fix and verification details.

## Using IR

If you included IR, use an ordinary Consumer IR app such as IR Blaster.
No root, private test app or E-Ink accessibility setting is needed for IR.
Current support is **one NEC/NECext frame** at nominal **38000 or 38222 Hz**.
Both values select the same built-in controller carrier, not independently
measured frequencies. Other protocols, standalone repeat frames and bundled
repeat sequences are rejected. Learning is not a supported user feature.
An API success does not confirm that the appliance received the command.

Test apps previously installed in userdata may remain after an image update.
Remove them separately in Android app settings if no longer needed.
