# HiBreak Pro E-Ink service

Android E-Ink accessibility service, native daemon, and offline GSI patching
tools for the **Bigme HiBreak Pro (black-and-white, MT6877)**.
The working configuration uses the **stock vendor**, not the HiBreak Pro
Color HWC shim.

## Using an EvoX Treble GSI

**Start with the [install guide](Guide.md).** It covers backup, unlocking,
first install, setup and updates. [Building and flashing](docs/BUILDING.md)
has the details for building the app, daemon and patched image.

> **Press Power after every restart.** Every time the phone restarts or powers
> up, press Power once right after the Bigme logo flashes, otherwise it can go
> back to powered-off. This is a known issue and is not fixed.

- [Findings and troubleshooting](docs/FINDINGS.md): tested hardware/software,
  display fixes, stock mode research, AOD, boot/power evidence, limitations,
  and failed approaches.
- [EvoX releases](https://github.com/Doze-off/EvoX_treble/releases):
  tested input `EvoX-11.11-GSI_treble_arm64-ab-MICROG-20260920.img`.
- [Original HiBreak release](https://github.com/vbbot/HibreakProPatchingService/releases/tag/20250507):
  source of the prebuilt APK used by the offline APK patcher.

The patched EvoX display and app have worked on one device with stock 3.1.6
vendor. This is not a guarantee for other firmware, GSIs, or the Pro Color.
Some app controls remain unsupported. Back up the exact stock firmware first.
**Do not use the Hisense A9 system-image patcher unchanged.**

### Tools

| Script | Purpose |
|--------|---------|
| [build-apk.sh](tools/build-apk.sh) | Rebuild the tested prebuilt APK with five modes, toolbar fix, and AOD switch |
| [build-daemon.sh](tools/build-daemon.sh) | Compile the current daemon with the Android NDK |
| [patch-gsi.sh](tools/patch-gsi.sh) | Install display/ADB/AOD scripts, APK, daemon, and permissions into an ext4 GSI |
| [flash-system.sh](tools/flash-system.sh) | Dry-run by default; `--flash` checks fastbootd and active slot |
| [collect-diagnostics.sh](tools/collect-diagnostics.sh) | Save read-only boot, power, display, and service diagnostics |

No tool downloads dependencies, wipes data, patches vendor, or flashes
automatically. Large inputs, generated images, logs, and local tools belong
in git-ignored `local/` and `build/`. AOSP build modules remain available
as an alternative to the prebuilt-APK route.

## Default button mappings

- **Single press E-Ink button** — refresh screen
- **Double press E-Ink button** — open E-Ink menu with per-app refresh modes

These mappings can be changed in the E-Ink Settings app.

## HiBreak refresh modes

The popup and default-mode preference offer the same five modes:

| Mode | Driver value | Daemon command | Saved preference value |
|------|--------------|----------------|------------------------|
| HD | 177 | `s` | 2 |
| Regal | 180 | `c` | 0 |
| Fast | 178 | `b` | 1 |
| Extreme | 179 | `p` | 3 |
| Hyper | 183 | `h` | 4 |

The selector and popup use this order. Existing saved values and per-app
choices retain their meanings; the displayed order does not change their
stored mode values. Hyper needs the matching updated daemon. It is a mode
exposed by the stock 3.1.6 framework, not a guaranteed increase in refresh
speed on every GSI.

The settings activity uses an in-layout toolbar above the preference list
and fits system-window insets, so the title cannot cover the first settings
on edge-to-edge Android versions.

### Settings

- Button mappings are shown **top button first, then bottom button**. Existing
  mappings are unchanged.
- Expand **Per-App Refresh Modes > Advanced** to choose a mode for each installed
  launcher app. **Use default** removes its override. These are the same saved
  modes used by the popup; selecting a mode there can replace an app's choice.
  Modes apply when switching to the app, while the accessibility service is
  enabled. **Disable Per-App Refresh Mode** temporarily uses a shared mode
  without deleting the saved per-app choices.
- **Default Refresh Mode** remains editable with per-app modes enabled and is
  used for apps without an override.
- **Color Scheme** changes Android's system palette and compatible apps' dynamic
  colours, not the panel waveform or refresh mode. On the monochrome HiBreak,
  colours appear as greys. `SPRITZ` is the muted/near-monochrome style.
- **Override Max Brightness** is disabled on HiBreak: its legacy command only
  sets `sys.linevibrator_touch`, not the frontlight driver or slider limits.
  Use the popup's independent cold/warm frontlight sliders (0–254).

## Always-On Display inversion

**EInk Service Settings → Invert colours on Always-On Display** (on by
default) controls whether the GSI's `hibreak-aod.sh` inverts colours while
dozing. The app sends `aoi1`/`aoi0` to the daemon, which sets
`persist.sys.hibreak.aod_invert` to `true`/`false`; the setting is re-sent
whenever the accessibility service connects.

The legacy static-lockscreen icon, opacity, background and colour controls,
including the popup opacity row, are removed/hidden on HiBreak. They use
`sys.linevibrator_type` and an unsupported bitmap path, not Android SystemUI AOD.
Seeing an image briefly during boot does not establish that those controls work.
Configure the actual AOD in Android's lockscreen settings; inversion remains a
separate supported workaround.

## Licensing

### MIT License

Most of the project is licensed under the MIT License unless specified
otherwise.

The code and releases are provided “as is,” without any express or implied
warranty of any kind including warranties of merchantability,
non-infringement, title, or fitness for a particular purpose.

### Apache License 2.0

The file `HardwareGestureDetector.kt` includes code derived from AOSP. The
original code is subject to the following license:

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

Modifications and additions to the original code are licensed under the MIT
License.
