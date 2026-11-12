# Research notes

Observed on one black-and-white HiBreak Pro during October–November 2026.
Distinguish working configurations from experiments; these notes do not
establish support for the HiBreak Pro Color or every vendor revision.
Current, actionable conclusions live in [reference/](../README.md#reference--how-things-work);
these pages keep the dated evidence behind them.

## Recent findings (2026-11-11)

- Property-only refresh-mode selection was reported working, but the
  property-only Auto Refresh experiment was not. The tested init bridge for
  Auto Refresh and Anti-Shake worked and is now the default. Bridge requests
  are asynchronous and do not acknowledge a successful hardware write.
- The user reported that the enforcing e-ink daemon image worked after the
  specific `system_server` Binder callback grant was added. The separate
  enforcing display/AOD helper image was also reported working, with AOD
  inversion retained. These reports are not a complete feature-by-feature
  regression matrix. See the [migration investigation](../reference/verification.md#migration-investigation-history).
- For the tested EvoX/stock-vendor merge, the 70-grant PHH reduction leaves
  371 ordinary and 15 extended neverallow diagnostic blocks. The combined
  release policy added none, but `phhsu_daemon` remains permissive; this is
  not a claim that upstream PHH services are migrated or hardened.
- The release builder now patches one working image and validates the combined
  policy, file contents and metadata, and filesystem before publication.
  Necessary intermediate policy compilations are retained. The tested host
  build took about 106 seconds versus 465 seconds for an earlier per-stage
  build with the same GSI, vendor, and reused APK; timings are host-specific.
  The resulting 21 changed files matched the strict image in content and
  metadata. Host verification is not a new device test. See
  [reproducibility](display/reproducibility.md) and the [build guide](../build/build-image.md).

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
