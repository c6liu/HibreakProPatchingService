# Research notes

Observed on one black-and-white HiBreak Pro during October–November 2026.
Distinguish working configurations from experiments; these notes do not
establish support for the HiBreak Pro Color or every vendor revision.
Current, actionable conclusions live in [reference/](../README.md#reference--how-things-work);
these pages keep the dated evidence behind them.

## Display, boot and apps

- [composer-crash.md](display/composer-crash.md) — vendor composer `processImage` SIGSEGV and soft restart
- [first-lock-crash.md](display/first-lock-crash.md) — first unlock/lock crash timelines, ColorFade and first-sleep tests
- [boot-and-power.md](display/boot-and-power.md) — power-button-after-boot report, wake helper experiments
- [camera-preview.md](display/camera-preview.md) — Aperture preview pauses
- [xrz-graphics-policy.md](display/xrz-graphics-policy.md) — stock vs GSI `vendor.xrz.*` policy and XRZ overlay checks
- [third-party-apps.md](display/third-party-apps.md) — Kindle storage and Outlook login issues
- [failed-approaches.md](display/failed-approaches.md) — what did not work; do not repeat blindly
- [reproducibility.md](display/reproducibility.md) — script locations, validation, external references

## Infrared

Start with the [IR overview](ir/README.md) (conclusion, inputs and limits).

- [hxdir-transport.md](ir/hxdir-transport.md) — HxdIR transport and packet generation
- [codec-normalization.md](ir/codec-normalization.md) — recovered normalization rules, repeats, carriers
- [extended-records.md](ir/extended-records.md) — extended/database packets and learned data
- [protocol-correlation.md](ir/protocol-correlation.md) — known-protocol correlation, binary landmarks
- [android-ir-stack.md](ir/android-ir-stack.md) — why Android advertises IR, app integration, access
- [stock-kernel-driver.md](ir/stock-kernel-driver.md) — stock `ctrl` driver and ioctl contract
- [hxd019-variants.md](ir/hxd019-variants.md) — stock resources, public HXD019 sources, variants
- [historical-diagnostics.md](ir/historical-diagnostics.md) — v1–v6 test results (not release features)
- [limitations.md](ir/limitations.md) — remaining limitations and read-only checks
- Current adapter contract: [reference/ir-adapter.md](../reference/ir-adapter.md)
