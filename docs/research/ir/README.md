# HiBreak Pro IR compatibility investigation

This investigation began with read-only APK, kernel and stock-firmware
analysis. Later, with explicit authorization, test ROMs were built and
transmission was tested on-device. The current result is an opt-in
[NEC/NECext Android IR adapter](../../reference/ir-adapter.md#experimental-standard-android-nec-adapter).
The user confirmed that a fixed TCL Volume Up command worked through the
test app and later that IR Blaster worked through the standard API adapter.
Those are user-reported appliance results, not independent optical
measurements. This document distinguishes static findings, on-device
observations and user reports.

Device results are from one black-and-white HiBreak Pro using stock 3.1.6
vendor (`Bigme_HiBreak_V1.0_20260306`) with the tested EvoX image. The
LineageOS release configuration and other vendor firmware versions have not
been validated on-device; do not infer compatibility from this report.

## Conclusion

The HiBreak Pro has an existing HXD019-family IR driver, but its working
application and its advertised Android IR HAL use different interfaces:

```text
HxdIR button / learned code
  -> native HXD packet generation
  -> ETIO / libet_jni_io.so
  -> /dev/ctrl
  -> existing ctrl driver, bound to hxd019_ir

This app's Internal transmitter
  -> ConsumerIrManager
  -> consumer_ir framework service
  -> android.hardware.ir@1.0::IConsumerIr/default
  -> stock consumerir.common.so
  -> /dev/lirc0 (not present on the connected device)
```

The stock-module implementation was inspected in a backup, not read
directly from the running HAL; SELinux denied ADB access to that library.
The running service identity and reported frequency table agree with the
backup. On the inspected firmware, the stock module targets `/dev/lirc0`,
while the working HXD transport uses `/dev/ctrl`.

**Current implementation:** the system-image overlay replaces the module
visible to the existing Android IR service with an experimental adapter.
Ordinary `ConsumerIrManager` apps can request supported NEC/NECext frames;
the adapter translates these into HXD packets for `/dev/ctrl`. This has
been reported working with the TCL test command and IR Blaster. See the
adapter section for the exact contract and its qualifications.

This is deliberately **not a generic waveform adapter**: it accepts one
full NEC/NECext frame per call and canonicalizes its timing. Only nominal
38000 and 38222 Hz requests are accepted, and both select the same
controller-built carrier. Exact optical carrier/timing, repeat behavior
and other protocols remain unverified. The controller does not expose a
generic Android timing/carrier API in the inspected kernel paths.

Learning is not possible: the user reported that the phone has no IR
receiver hardware. The attempted learning tests on the inspected firmware
returned the same data for a button press and a no-button control; see the [historical experiment summary](historical-diagnostics.md). Do not
treat a nonempty capture or successful device write as proof of signal
reception or optical output.

No new kernel driver appears necessary for the existing HxdIR path.
Static analysis can recover the app-side record transformations without IR
measurement equipment. General arbitrary-waveform compatibility remains
conditional on mapping those records to Android timings and carriers;
measurement is needed to validate physical output, not to continue APK
analysis.

The recovered stock kernel confirms a bit-banged controller transport:
its ioctls drive individual GPIOs, and its initialization sends no
carrier/timer configuration packet. It does not expose a hidden generic
IR timing API. See [the stock driver trace](stock-kernel-driver.md)
for the exact read commands, byte limit, and error semantics.

A public document describes an SCL-controlled IR-envelope mode for newer
controller variants, but does not establish support or safe control on this
phone. It is not used by the adapter. See
[the variant/source analysis](hxd019-variants.md)
if this becomes a future investigation.

## Inputs and limits

- Supplied APK: `HxdIR.apk` (analysis input; not copied into this repository).
- Package: `ht.song.remotestar.hxd`.
- Version: `88.17.101`, version code `8817101`.
- Minimum SDK: 18; target SDK: **27**; compile SDK: 30.
- APK SHA-256:
  `02217864bc97f74eb9c2c946f09aaa29e8aa08b9f330d48f8976fc58ac35e770`.
- Current app source revision:
  `c2fbf7887d594fd795393d0d7847771bc9ab9b2f`.
- Read-only ADB inspection of the connected black-and-white MT6877 device:
  Android 16/API 36, kernel `4.19.191`, SELinux **Enforcing**.
- Existing stock 3.1.6 backup: selected libraries from
  `extracted-vendor/vendor_a.img`, and the kernel from `boot_a.bin`.
  Extraction used read-only `debugfs` and host-side gzip decompression;
  no image was mounted, patched, or flashed.

The user reports HxdIR works on this device. Neither HxdIR nor this app's
package was found in the user-0 package queries during this inspection.
Therefore the supplied APK's built-in path was inspected statically; the
active transport selection of a running HxdIR instance was not observed.
No personal remote database or unrelated application data was accessed.
