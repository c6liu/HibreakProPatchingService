# HiBreak Pro E-Ink service

This repository contains Android build modules for an E-Ink accessibility
service and its native daemon, intended for integration into a compatible GSI
build. The Android modules and product make fragment are in this repository;
there is no generic `patch_system_img.sh` image-patching script here.

## Using an EvoX Treble GSI

The HiBreak Pro guide documents direct flashing of a Treble GSI. The current
[EvoX Treble releases](https://github.com/Doze-off/EvoX_treble/releases)
include an Android 16 QPR2 `arm64-ab` image. See
[Guide.md](Guide.md) for the HiBreak Pro-specific image selection and
fastbootd steps. This is a generic GSI, not a HiBreak Pro-specific build, and
the Android 16 EvoX release has not been verified on this device.

The [HiBreak Pro XDA thread](https://xdaforums.com/t/bigme-hibreak-pro-dimensity-900-mt6877-e-ink-phone.4723924/)
has community notes about mtkclient backups and a stock recovery package.
That package is identified as firmware 1.9.6 from 2025-04-03; only use its
partition images if they match the stock build on your device. See
[Guide.md](Guide.md) for details and recovery cautions.

Flashing the unmodified GSI installs EvoX, but does not by itself include this
repository's service and daemon. To add the E-Ink app, daemon, and policy,
these modules need to be integrated into and built with the GSI, or included
through a separately verified patching/release process. The old A9 patcher
mentioned by earlier versions of this README is a third-party artifact; its
compatibility with HiBreak Pro, EvoX, or Android 16 is not established here.
Do not assume that patcher contains the code in this repository.

The daemon also contains device-specific sysfs paths. The HiBreak Pro guide
documents refresh-mode and backlight nodes, but the daemon's Qualcomm-specific
E-Ink commit, threshold, and contrast paths have not been verified on this
device. See the compatibility notes in [Guide.md](Guide.md) before expecting
all controls to work.

## Default button mappings

- **Single press E-Ink button** — refresh screen
- **Double press E-Ink button** — open E-Ink menu with per-app refresh modes

These mappings can be changed in the E-Ink Settings app.

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
