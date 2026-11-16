# Build a patched image

Follow these pages in order. Building never flashes a phone; when you have a
final image, install it using the [Guide](../../Guide.md).

The [unified entry point](build-image.md) is `tools/build/build-release.py`.
It builds/signs the source APK automatically, then builds the daemon and image.
The tested-device defaults include IR, XRZ and the enforcing migrations;
`--compatibility` disables them for other GSIs. `--built-apk` reuses a signed
APK without rebuilding it. APKs are built only from checked-in source; the
upstream APK patcher has been removed. Device validation remains required.

1. [Set up a build computer](host-setup.md)
2. [Download build tools and input images](inputs.md) — NDK, signer, GSI, Gradle/SDK
3. [Prepare IR build inputs](ir-inputs.md) — matching stock vendor image for IR or XRZ; AOSP headers for IR
4. [Set up APK signing](signing.md)
5. [Build a release image](build-image.md)
6. [Select and check the final image](build-image.md#select-and-check-the-final-image)

Other build topics:

- [IR overlay](ir-overlay.md) — optional manual alternative to the default IR stage
- [XRZ v2 overlay](xrz-overlay.md) — optional manual alternative to the default XRZ stage; crash fix unproven
- [Source-built APK](inputs.md#source-apk-prerequisites) — standalone Gradle build; device validation required
- [Tests](tests.md) — host tests and opt-in device tests

Do not reapply an overlay to an image that already includes it.

Details of what each tool does are in [reference/](../README.md#reference--how-things-work),
for example [patcher behavior](../reference/patcher.md) and the
[flashing helper](../reference/flashing.md).
