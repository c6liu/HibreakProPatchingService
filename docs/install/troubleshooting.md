# Troubleshooting

| Problem | What to do |
|---------|------------|
| Terminal closes after a failed command | Do not use `set -euo pipefail` interactively. Open a terminal, return to the project folder and set your variables again. |
| `Missing dependency` / `command not found` | Recheck [computer setup](prepare-computer.md), [build setup](../build/host-setup.md) and [build inputs](../build/inputs.md). NDK tools come from Google; `secilc` and `readelf` come from distro packages. |
| Missing `hardware/consumerir.h`, `cutils/...` or `system/graphics...` | Check `AOSP_HEADERS` and all three include directories from [IR build inputs](../build/ir-inputs.md). |
| `Refusing to overwrite` / output already exists | Choose new output names consistently. Do not delete the original GSI or your only working image. |
| Signing fingerprint mismatch | Inspect `keytool -list -v` for the selected alias and set its SHA256 fingerprint. Do not bypass verification. |
| `adb` says `unauthorized` | Unlock the phone and accept its authorization dialog. |
| USB permission denied | Follow Google's Linux device setup and mtkclient's udev instructions; reconnect after applying rules. |
| Phone turns off after restart | Press Power right after the Bigme logo flashes, every time. |
| `reap_urb` / `Protocol error` during flash | System may be incomplete. Stay in fastbootd, check `fastboot devices`, reconnect with a direct port/good cable and retry the complete system flash. Do not reboot or wipe first. |
| `Invalid sparse file format at header magic` | Alone, this can be harmless while fastboot converts a raw image. The entire flash must still finish successfully. |
| Recovery says "Can't load Android system" on first install | After confirming the system flash succeeded, use **Factory data reset**; this erases data. |
| IR app reports no emitter | Confirm you flashed the IR image, not just the display base. A test APK alone cannot add the HAL. |
| Screen stops updating while touch still works (for example after choosing Natural colors or adjusting the frontlight) | Enable **Treble Settings → Display settings → Disable HW overlays**. Then confirm `adb shell dumpsys SurfaceFlinger` reports `h/w composer disabled`. |
| IR emitter exists but the appliance does not respond | Check NEC/NECext, carrier alias and repeat settings. Changing frequency cannot turn an unsupported protocol into NEC. |

For display/app problems, enable USB debugging and collect read-only logs:

```bash
tools/device/collect-diagnostics.sh build/diagnostics
```

See [Findings](../research/README.md) and [detailed building/verification](../build/README.md)
before making additional device changes.

**Return to stock slot B:** only if you left its stock partitions intact,
enter bootloader mode and run `fastboot --set-active=b`, then
`fastboot reboot`. Shared userdata may be incompatible and need a factory
reset. This is not a substitute for a full backup; use the mtkclient recovery
instructions for a complete restore.

## Reference guides

- Google: [ADB](https://developer.android.com/tools/adb),
  [Linux device setup](https://developer.android.com/studio/run/device#setting-up),
  [NDK installation](https://developer.android.com/studio/projects/install-ndk),
  [APK signing](https://developer.android.com/studio/publish/app-signing).
- Device-specific community author:
  [HiBreak Pro GSI notes](https://vbh.ai/hibreak-pro-gsi-release/),
  [backup/unlock guide](https://vbh.ai/unlocking-the-bootloader-and-rooting-the-hibreak-pro/),
  [Android 15 installation background](https://vbh.ai/hibreak-pro-guide-4-flashing-the-android-15-gsi/).
  Those older articles explain the device; use this repository's commands
  for the current Android 16 workflow.
- [mtkclient's own documentation](https://github.com/bkerler/mtkclient).
- [IR investigation and exact limitations](../research/ir/README.md).
