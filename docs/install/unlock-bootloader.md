# Unlock the bootloader (first installation only)

**This erases the phone.** Skip this page if it is already unlocked.
On the phone, enable Developer options (tap **Build number** seven times),
then enable **OEM unlocking** and **USB debugging**.
Connect USB, unlock the screen, and accept the computer authorization prompt.

```bash
adb devices
```

The phone should be listed as `device`. If it says `unauthorized`, accept the
prompt. If it is absent, fix the cable/USB permissions first. Then:

```bash
adb reboot bootloader
fastboot devices
fastboot flashing unlock
```

Confirm the unlock on the phone. After it restarts, remember the Power-button
workaround. Complete enough stock setup to re-enable USB debugging and
authorize the PC. Google's
[ADB documentation](https://developer.android.com/tools/adb) and the
[HiBreak-specific unlock guide](https://vbh.ai/unlocking-the-bootloader-and-rooting-the-hibreak-pro/)
explain these modes in more detail.
