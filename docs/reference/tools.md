# Tools reference

The scripts are developer and maintenance tools. For the supported image
workflow, follow the [build guide](../build/README.md), which builds the
release APK, daemon and patched image in order. The
[release orchestrator](../../tools/build/build-release.py) uses one working image
and records input/output checksums and stage timings in a manifest. Script
paths have changed: use the directories below rather than the old `tools/`
top-level paths.

## Build entry points

| Script | Purpose |
|--------|---------|
| [build-release.py](../../tools/build/build-release.py) | Unified release build with combined or strict verification; never flashes |
| [build-source-apk.sh](../../tools/build/build-source-apk.sh) | Build the checked-in Kotlin/resources with Gradle and the APK signer |
| [build-daemon.sh](../../tools/build/build-daemon.sh) | Compile the current daemon with the Android NDK |
| [build-ir-hal.sh](../../tools/build/build-ir-hal.sh) | Build the single-frame NEC/NECext Consumer IR adapter used by the default release |
| [build-ir-api-test.sh](../../tools/build/build-ir-api-test.sh) | Build an ordinary `ConsumerIrManager` test client; no root or private properties |

## Standalone image tools

These are manual alternatives, not extra steps after a default release build.

| Script | Purpose |
|--------|---------|
| [patch-gsi.sh](../../tools/image/patch-gsi.sh) | Patch display/AOD support, preserve saved ADB state, enforce ADB authorization, and remove `su` unless `--root`; supports `--release` mode |
| [patch-gsi.py](../../tools/image/patch-gsi.py) | Python implementation of the base image patcher |
| [add-ir-hal-to-gsi.py](../../tools/image/add-ir-hal-to-gsi.py) | Add the NEC IR HAL and optionally the API test app; `--check-only` does not write an image |
| [add-xrz-compat-to-gsi.py](../../tools/image/add-xrz-compat-to-gsi.py) | Add the XRZ v2 graphics-property overlay; requires a matching vendor, `secilc` and SETools |
| [add-phh-reduction-to-gsi.py](../../tools/image/add-phh-reduction-to-gsi.py) | Apply or preflight the exact-input experimental PHH grant reduction |

## Device tools

| Script | Purpose |
|--------|---------|
| [flash-system.sh](../../tools/device/flash-system.sh) | Dry-run by default; `--flash` checks fastbootd and active slot; `--wipe-data` opts into erasing shared userdata |
| [collect-diagnostics.sh](../../tools/device/collect-diagnostics.sh) | Save read-only boot, power, display, and service diagnostics |

## Diagnostics and internals

| Location | Purpose |
|----------|---------|
| [check-eink-migration.py](../../tools/diagnostics/check-eink-migration.py) | Host-only e-ink policy and permission validation |
| [verify-hxd-codec.py](../../tools/diagnostics/verify-hxd-codec.py), [verify-hxd-driver.py](../../tools/diagnostics/verify-hxd-driver.py) | Optional IR research harnesses |
| [internal/](../../tools/internal/) | Release-init and build-property helpers invoked by the patcher |
| [hibreak/](../../tools/hibreak/) | Shared image, policy, verification and release-pipeline modules |
| [display/](../../tools/display/), [ir/](../../tools/ir/) | Android runtime scripts, policies, init files and IR sources |
| [tests/](../../tools/tests/) | Host tests and native fixtures |

The Gradle source builder resolves dependencies and can install
missing SDK components; the other tools do not download dependencies. No tool
patches vendor or flashes automatically. A flash requires an explicit `--flash`;
erasing shared userdata also requires
`--wipe-data`. See [flashing helper reference](flashing.md) before using the
flash script. AOSP build modules remain available as an alternative to the
standalone Gradle route, but the AOSP module route is currently **unmaintained and
untested**. The checked-in module definitions and sources are retained for
reconstruction; use the documented Gradle source path for supported builds.

IR learning is not possible on the tested phone: it has no IR receiver.
The former capture and private transmit diagnostics have been removed; see the
[historical diagnostic results](../research/ir/historical-diagnostics.md).
