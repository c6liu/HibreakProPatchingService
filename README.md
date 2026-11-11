# HiBreak Pro E-Ink service

Android E-Ink accessibility service, native daemon, and offline GSI patching
tools for the **Bigme HiBreak Pro (black-and-white, MT6877)**. The working
configuration uses the **stock vendor**, not the HiBreak Pro Color HWC shim.

## Using an EvoX Treble GSI

**Start with the [install guide](Guide.md).** It covers backup, unlocking,
first install, setup and updates. The [build guide](docs/build/README.md)
covers building the app, daemon and patched image. All documentation is
indexed in [docs/](docs/README.md).

> **Press Power after every restart.** Every time the phone restarts or powers
> up, press Power once right after the Bigme logo flashes, otherwise it can go
> back to powered-off. This is a known issue and is not fixed.

- [Research notes](docs/research/README.md): tested hardware/software,
  display fixes, stock mode research, AOD, boot/power evidence, limitations,
  and failed approaches.
- [HiBreak Pro IR investigation](docs/research/ir/README.md): HXD019 and Android
  IR interfaces, APK codec analysis, and ROM-side HAL integration constraints.
- [EvoX releases](https://github.com/Doze-off/EvoX_treble/releases):
  recommended GSI input `EvoX-11.11-GSI_treble_arm64-ab-MICROG-20260920.img`.
- [Prebuilt patched EvoX release](https://github.com/c6liu/HibreakProPatchingService/releases/tag/v0.2.0):
  download the release asset and follow the prebuilt route in [Guide.md](Guide.md#use-a-prebuilt-release-image).
- [Original HiBreak release](https://github.com/vbbot/HibreakProPatchingService/releases/tag/20250507):
  historical reference for the original HiBreak integration.

The display fixes have worked with both LineageOS 23.2 and EvoX 11.11 on one
device with stock 3.1.6 vendor. Ordinary-app NEC IR has been tested on EvoX.
The fully patched LineageOS image has not yet been checked on the device.
These results are not a guarantee for other firmware, GSIs, or the Pro Color.
Some app controls remain unsupported. Back up the exact stock firmware first.
**Do not use the Hisense A9 system-image patcher unchanged.**

## Settings and tools

- [Settings reference](docs/reference/settings.md): button mappings, refresh
  modes, per-app controls, frontlight and AOD behavior.
- [Tools reference](docs/reference/tools.md): scripts and their purposes.
- [Build guide](docs/build/README.md): ordered instructions for building an
  image from source.

The [unified release builder](docs/build/build-image.md) builds and signs the
source APK, compiles the daemon, and creates a new image. Add `--ir --xrz` for
the IR HAL and experimental graphics-property overlay, or use `--built-apk`
to reuse an already signed source-built APK. APKs are built only from the
checked-in Kotlin/resources; upstream binary APK patching is no longer supported.
Source-APK device validation remains required.

The tools do not patch vendor or flash automatically. Flashing is a dry run
unless explicitly requested; a data wipe requires an explicit option and
erases shared userdata. Large inputs, generated images, logs, and local tools
belong in git-ignored `local/` and `build/`. IR learning is not supported on
the tested phone; the earlier capture path is a legacy development diagnostic
([details](docs/research/ir/historical-diagnostics.md)).

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
