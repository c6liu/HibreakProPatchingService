# Build a patched image

Follow these pages in order. Building never flashes a phone; when you have a
final image, install it using the [Guide](../../Guide.md).

1. [Set up a build computer](host-setup.md)
2. [Download build tools and input images](inputs.md) — NDK, apktool, signer, GSI, base APK
3. [Prepare IR build inputs](ir-inputs.md) — *IR only*: matching stock vendor image, AOSP headers
4. [Set up APK signing](signing.md)
5. [Build a release image](build-image.md)
6. [Add IR support to an image](ir-overlay.md) — *optional*
7. Select and check the final image — end of [Build a release image](build-image.md#select-and-check-the-final-image)

Other build topics:

- [Experimental XRZ graphics-property overlay](xrz-overlay.md) — untested on-device fix attempt
- [Tests](tests.md) — host tests and opt-in device tests

Details of what each tool does are in [reference/](../README.md#reference--how-things-work),
for example [patcher behavior](../reference/patcher.md) and the
[flashing helper](../reference/flashing.md).
