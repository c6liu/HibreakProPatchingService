# Stock refresh modes

Examined the local stock backup's `framework.jar`, `xrz.framework.server.jar`,
xSettings and MediaTek SystemUI with apktool smali. Relevant classes:

- `xrz.framework.manager.XrzEinkManager`
- `EinkRefreshMode`
- `com.xrz.settings.einkcenter.RefreshModeDialog`, `EinkCenterDialog`,
  `AppRefreshSetDialog`, `EinkUiHelper`
- `DisplayPolicyController`, using `XrzEinkManagerInternal.setLayerRefreshMode`

The following mode values are reported in the
[community framework analysis](https://www.reddit.com/r/Bigme/comments/1jvij9x/guide_more_hacks_for_the_hibreak_pro_fix_android/).
Their presence in the stock framework does not establish that each mode works
as a global mode on the GSI. The app still exposes only the five modes below.

| Mode | Decimal |
|------|---------|
| INIT | 1 |
| DU | 2 |
| GC16 | 4 |
| GC4 | 8 |
| A2 | 16 |
| GL16 | 32 |
| GLR16 | 64 |
| GLD16 | 128 |
| GU16 | 132 |
| GU4 | 136 |
| INPUT | 137 |
| CLEAN | 176 |
| HD | 177 |
| NORMAL | 178 |
| FAST | 179 |
| REGAL | 180 |
| HANDWRITE | 1029 |
| RUBBER | 1030 |
| AUTO | 32768 |
| HD_256 | -2147483471 (signed), 2147483825 (unsigned; 0x800000b1) |

HYPER (183) is also exposed by the stock dialog. `EINK_DEFAULT_MODE` is read
from `ro.vendor.xrz.default_refresh_mode`, with a fallback of 0; NORMAL (178)
is not necessarily the device's configured default. `EINK_RECT_MODE` (1024)
and the following HWC values are flags or effects, not standalone refresh modes:

| Flag or effect | Decimal |
|----------------|---------|
| SURFACEVIEW | 65536 |
| FORCE_REFRESH | 131072 |
| HANDWRITTEN | 262144 |
| HOME | 524288 |
| HANDWRITTEN_BG | 1048576 |
| MULTI_DAMAGE | 2097152 |
| INPUT_METHOD | 4194304 |
| AUTO_DITHER | 8388608 |
| DISABLE_LAYER | 16777216 |
| OVERLAY | 33554432 |
| LOGO | 67108864 |
| CURSOR | 134217728 |
| DITHER_TEXT_EFFECT | 536870912 |
| DITHER_PICTURE1_EFFECT | 1073741824 |
| DITHER_PICTURE2_EFFECT | 1610612736 |
| DITHER_256_EFFECT | -2147483648 |
| SKIP_FRAME | -1 |

The correct flag combinations and their behavior on the GSI have not been
verified; do not assume they can be used as global mode values.

The stock dialog lists **HD 256, Regal, Fast, Extreme, Hyper**. The patched app
uses the order **HD, Regal, Fast, Extreme, Hyper**:

| App label | Old label | Driver value | Command | Saved value |
|-----------|-----------|--------------|---------|-------------|
| Regal | Clear | 180 | `c` | 0 |
| Fast | Balanced | 178 | `b` | 1 |
| HD | Smooth | 2147483825 (`0x800000b1`, HD_256) | `s` | 2 |
| Extreme | Speed | 179 | `p` | 3 |
| Hyper | new | 183 | `h` | 4 |

The app label remains **HD**, but command `s` now requests the stock flagged
**HD_256** value rather than plain HD 177. The old preference indices and per-app
selections are preserved. Update the daemon in the image for this mapping to take
effect. Physical 256-level output on the GSI has not yet been verified.
Hyper is a stock-exposed mode, not a guaranteed speed boost.

## Changing modes over ADB

On stock firmware, the community guide suggests setting the vendor property
directly, for example:

```bash
adb shell setprop vendor.xrz.global_refresh_mode 16  # A2
adb shell setprop vendor.xrz.global_refresh_mode 8   # GC4
adb shell setprop vendor.xrz.global_refresh_mode 136 # GU4
adb shell setprop vendor.xrz.global_refresh_mode 178 # NORMAL
```

These are alternatives, not a sequence to run together. A normal ADB shell
may lack permission to set the vendor property; `getprop` can show the current
property value, but does not confirm that the display applied it.

The GSI daemon writes both
`/sys/kernel/debug/eink_debug/global_mode` and
`vendor.xrz.global_refresh_mode`. The stock `hwcomposer.mt6877.so` references
the vendor property. On a GSI diagnostic build with the `eink_gsi.rc`
diagnostic bridge installed, request an override without interactive su:

```bash
adb shell setprop debug.hibreak.refresh_mode 136
adb shell getprop vendor.xrz.global_refresh_mode
```

The bridge is removed from release images. Setting the debug property alone
does not confirm that the privileged property and sysfs writes succeeded, or
that a given mode is supported. The app daemon provides commands only for the
five app mode values shown above. The enforcing-candidate control bridge also
accepts only those values, not arbitrary community mode values.
The accessibility service may overwrite that diagnostic value when switching
apps. Disable per-app modes while comparing speed. Auto-refresh (`clean_a2`)
and anti-flicker can also alter perceived speed/ghosting. No new waveform,
higher panel frequency or benchmarked speed guarantee is supplied.

Stock per-layer policy/native framework APIs are not fully reproduced by
global sysfs/property writes. The stock control-center APK depends on Bigme
framework services and is not a standalone app usable on arbitrary GSIs.
The backup remains the source of research evidence; proprietary stock APKs
and decompiled framework trees are not included in this repository.
