# Tested baseline and scope

This procedure is for the black-and-white HiBreak Pro, MT6877, stock vendor
3.1.6 / `Bigme_HiBreak_V1.0_20260306`, kernel 4.19.191. The recommended
Android 16 input is Doze-off's
`EvoX-11.11-GSI_treble_arm64-ab-MICROG-20260920.img`, available from
[EvoX releases](https://github.com/Doze-off/EvoX_treble/releases). Its raw
image SHA-256 is:

```text
d25aeac2b42012e76e8f4fd95d69f9e28ceeac64289d85f194d72ef0249374bf  EvoX-11.11-GSI_treble_arm64-ab-MICROG-20260920.img
```

Use **arm64 A/B, ext4**. Extract compressed images first. Android sparse
images need `simg2img`; EROFS is not supported by this patcher or the tested
stock kernel. The display patcher requires a TrebleDroid `vndk.rc` using the
existing `phhsu_daemon` domain. It does not add a new SELinux policy or disable
SELinux. The optional [IR](../build/ir-overlay.md) and [XRZ](../build/xrz-overlay.md) overlays add scoped policy changes; they
do not disable SELinux. The display patcher does not install an IR HAL or add
`ctrl_device` access; standard Android IR transmission through the HXD019
driver is not included by default. A separate experimental, NEC-only adapter
is described in [Android IR adapter](ir-adapter.md).
See the [IR compatibility investigation](../research/ir/README.md) for the APK
analysis and ROM integration. Learning did not work on the tested phone:
button and no-button captures matched. Do not treat capture as a supported
user feature. The
standalone CLI and privileged capture/test-app paths are legacy, opt-in
development diagnostics; the HAL-only release does not install them. See
the [historical diagnostic results](../research/ir/historical-diagnostics.md).
The optional TCL test app is a fixed-command diagnostic, not a general
remote. The opt-in [NEC ROM adapter](ir-adapter.md#experimental-standard-android-nec-adapter)
accepts single-frame NEC/NECext requests through ConsumerIrManager
(38000 Hz and, since v8, the app's 38222 Hz nominal alias);
it rejects other protocols, repeat sequences, and frequencies. It is not
a general waveform HAL. The user reported the standard API test working
and later confirmed IR Blaster's NEC control; other protocols remain
unsupported.
Check other firmware/GSIs independently; do not assume compatibility.

The previously tested LineageOS image omits `persist.sys.usb.config` from
`system/build.prop`;
the patcher adds the MTP default when missing. Its
`system_ext/etc/build.prop` also sets `persist.sys.usb.config=adb` and
`ro.adb.secure=0` (ADB without computer authorization), and it ships a setuid
`/system/xbin/su`; the patcher fixes all three (see [GSI patcher behavior](patcher.md)). The display fixes
worked on the same-date LineageOS 23.2 SU build on the device, but this
microG image fully patched (app, daemon, AOD) has not yet been checked on the
device.

This pinned EvoX input
`EvoX-11.11-GSI_treble_arm64-ab-MICROG-20260920.img` (raw image SHA-256
`d25aeac2b42012e76e8f4fd95d69f9e28ceeac64289d85f194d72ef0249374bf`), still
patches and works, but Kindle cannot download books on it; see
[Findings](../research/display/third-party-apps.md).
