# First-boot setup

1. Complete Android setup.
2. Open **E-Ink Settings**, enable its accessibility service and allow
   **Display over other apps**.
3. Double-press the E-Ink button to open the refresh menu:
   **HD, Regal, Fast, Extreme, Hyper**.
4. Optional settings:
   - Choose separate single/double/long-press actions for the top and bottom
     buttons. To launch an app, choose **Launch App**, then its target in
     **App to launch** directly below. Screen-off launches wake the display
     but do not bypass the lock screen.
   - Choose per-app refresh modes or enable **Disable Per-App Refresh Mode**
     for one shared mode.
   - Set AOD inversion. Video refresh is experimental and opt-in per app.

USB debugging is not forced on by these release commands. Enable it in
Developer options when needed and authorize the PC on-screen. Updates
without a wipe preserve saved debugging settings and authorizations.

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
