# Tools reference

The scripts are developer and maintenance tools. For the supported image
workflow, follow the [build guide](../build/README.md), which builds the
release APK, daemon and patched image in order. The
[release orchestrator](../../tools/build-release.py) runs the same stages and
records input/output checksums in a manifest.

| Script | Purpose |
|--------|---------|
| [build-release.py](../../tools/build-release.py) | Unified release build: source APK/signing, optional signed source `--built-apk` reuse, daemon, IR/XRZ, and checksum manifest; never flashes |
| [build-source-apk.sh](../../tools/build-source-apk.sh) | Build the checked-in Kotlin/resources with Gradle and the APK signer |
| [build-daemon.sh](../../tools/build-daemon.sh) | Compile the current daemon with the Android NDK |
| [build-ir-tool.sh](../../tools/build-ir-tool.sh) | Build the HXD capture CLI with opt-in fixed-packet camera diagnostic; does not install a HAL |
| [add-ir-capture-to-gsi.py](../../tools/add-ir-capture-to-gsi.py) | Add the optional IR overlay; release support is HAL-only with `--hal-module`; diagnostics and test apps require opt-in; `--check-only` never packages an image |
| [add-xrz-compat-to-gsi.py](../../tools/add-xrz-compat-to-gsi.py) | Add experimental XRZ v2 labels for four exact graphics properties and restore composer set access; requires matching vendor, `secilc` and SETools; run after IR on a pre-XRZ image; `--check-only` never packages an image |
| [build-ir-remote.sh](../../tools/build-ir-remote.sh) | Build the standalone one-button IR test APK; requires the matching ROM overlay |
| [build-ir-hal.sh](../../tools/build-ir-hal.sh) | Build the experimental single-frame NEC/NECext Consumer IR adapter; opt in with overlay `--hal-module` |
| [build-ir-api-test.sh](../../tools/build-ir-api-test.sh) | Build an ordinary `ConsumerIrManager` test client; no root or private properties |
| [patch-gsi.sh](../../tools/patch-gsi.sh) | Patch display/AOD support, preserve saved ADB state, enforce ADB authorization, and remove `su` unless `--root`; supports `--release` mode |
| [flash-system.sh](../../tools/flash-system.sh) | Dry-run by default; `--flash` checks fastbootd and active slot; `--wipe-data` opts into erasing shared userdata |
| [collect-diagnostics.sh](../../tools/collect-diagnostics.sh) | Save read-only boot, power, display, and service diagnostics |

The Gradle source builder resolves dependencies and can install
missing SDK components; the other tools do not download dependencies. No tool
patches vendor or flashes automatically. A flash requires an explicit `--flash`;
erasing shared userdata also requires
`--wipe-data`. See [flashing helper reference](flashing.md) before using the
flash script. AOSP build modules remain available as an alternative to the
standalone Gradle route, but the AOSP module route is currently **unmaintained and
untested**. The checked-in module definitions and sources are retained for
reconstruction; use the documented Gradle source path for supported builds.

IR learning is not a supported feature on the tested phone. The capture path
is a legacy development diagnostic; see the
[historical diagnostic results](../research/ir/historical-diagnostics.md).
