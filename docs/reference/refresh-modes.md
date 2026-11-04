# Stock refresh modes

Examined the local stock backup's `framework.jar`, `xrz.framework.server.jar`,
xSettings and MediaTek SystemUI with apktool smali. Relevant classes:

- `xrz.framework.manager.XrzEinkManager`
- `EinkRefreshMode`
- `com.xrz.settings.einkcenter.RefreshModeDialog`, `EinkCenterDialog`,
  `AppRefreshSetDialog`, `EinkUiHelper`
- `DisplayPolicyController`, using `XrzEinkManagerInternal.setLayerRefreshMode`

Stock framework constants:

| Constant | Decimal | Hex |
|----------|---------|-----|
| CLEAN | 176 | 0xb0 |
| HD | 177 | 0xb1 |
| NORMAL | 178 | 0xb2 |
| FAST | 179 | 0xb3 |
| REGAL | 180 | 0xb4 |
| HYPER | 183 | 0xb7 |
| HD_256 | 2147483825 (unsigned) | 0x800000b1 |

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

The GSI daemon writes both
`/sys/kernel/debug/eink_debug/global_mode` and
`vendor.xrz.global_refresh_mode`. The stock `hwcomposer.mt6877.so` references
the vendor property. A normal shell cannot set all vendor properties; the
existing phh root domain can. To override for diagnosis without interactive su:

```bash
adb shell setprop debug.hibreak.refresh_mode 179
adb logcat -d -s a9EinkService
```

The accessibility service may overwrite that diagnostic value when switching
apps. Disable per-app modes while comparing speed. Auto-refresh (`clean_a2`)
and anti-flicker can also alter perceived speed/ghosting. No new waveform,
higher panel frequency or benchmarked speed guarantee is supplied.

Stock per-layer policy/native framework APIs are not fully reproduced by
global sysfs/property writes. The stock control-center APK depends on Bigme
framework services and is not a standalone app usable on arbitrary GSIs.
The backup remains the source of research evidence; proprietary stock APKs
and decompiled framework trees are not included in this repository.
