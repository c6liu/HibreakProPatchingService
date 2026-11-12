# Remaining IR limitations and next evidence

The bounded adapter is implemented and has user-reported success with the
TCL test command and IR Blaster. Do not describe the implementation as
generic or fully measured. Useful next work is limited to evidence that
would change its supported contract:

1. **Firmware compatibility:** the overlay is validated against a matching
   stock-vendor image, but the user's successful tests do not establish
   compatibility with other vendor, kernel or GSI versions. Validate each
   intended firmware combination on-device before claiming support.
2. **Optical waveform:** use a calibrated receiver/oscilloscope to measure
   carrier, mark/space timing and repeats for a known command. Camera-visible
   flashes and appliance response do not provide those measurements.
3. **Repeat behavior:** determine what the controller emits per accepted
   packet and test how ordinary apps express held keys. Current adapter
   accepts one full frame per call and rejects standalone/bundled repeat
   frames.
4. **Broader protocol support:** add a protocol only when its input
   recognition, HXD encoding and on-device result are validated. RC5/RC6,
   Sony, air-conditioner protocols and arbitrary timings remain unsupported.
5. **Learning:** not possible; the user reported that the phone has no IR
   receiver hardware. Existing button and no-button records matched.

The existing host suite covers framing, input bounds, controller errors,
serialization and the documented HAL/overlay contract. Passing those tests
does not replace validation on each target firmware or physical waveform
measurement.

## Read-only checks used

These Binder transaction numbers were checked on this Android 16 device;
they are not a portable interface for every Android release.

```sh
adb shell service check consumer_ir
adb shell service call consumer_ir 1
adb shell service call consumer_ir 3
adb shell pm list features
adb shell lshal
adb shell getenforce
adb shell ls -lZ /dev/ctrl /dev/lirc0
adb shell ls -la /sys/devices/platform/hxd019_ir
```

The missing-node error for `/dev/lirc0` is an expected finding, not something
to fix with a filesystem alias.

Further references:

- [ConsumerIrManager contract](https://developer.android.com/reference/android/hardware/ConsumerIrManager).
- [Android 16 ConsumerIrService source](https://github.com/aosp-mirror/platform_frameworks_base/blob/android16-release/services/core/java/com/android/server/ConsumerIrService.java).
- [ROM project](https://github.com/c6liu/HibreakProPatchingService).

The original report was added to the app repository; this copy is maintained
with the ROM patching project. No proprietary source, native library, kernel
image, or remote database was added to either repository.
