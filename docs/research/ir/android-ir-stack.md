# Android IR stack and app integration

Read-only Binder queries returned:

- `service call consumer_ir 1`: successful parcel with `hasIrEmitter = 1`.
- `service call consumer_ir 3`: 12 integers representing six singleton
  ranges: **30,000; 33,000; 36,000; 38,000; 40,000; 56,000 Hz**.
- PackageManager reports `android.hardware.consumerir`.
- `lshal` reports `android.hardware.ir@1.0::IConsumerIr/default`.
- The vendor IR service runs in `hal_ir_default`, as UID `system`.

The stock module contains exactly that static carrier table. Its transmit
routine opens `/dev/lirc0`, sets `LIRC_SET_SEND_CARRIER`
(`0x40046913`) and `LIRC_SET_SEND_DUTY_CYCLE` (`0x40046915`), then writes
32-bit pulse durations. It has no `/dev/ctrl` path or HXD packet encoder.

**Neither `/dev/lirc0` nor `/dev/irtx` exists on the inspected device.**
An `irtx_pwm` device-tree/platform entry exists, but it did not have the
driver binding seen on `hxd019_ir`; the entry alone does not prove a usable
PWM emitter.

Android's [ConsumerIrService](https://github.com/aosp-mirror/platform_frameworks_base/blob/android16-release/services/core/java/com/android/server/ConsumerIrService.java)
reports HAL availability, not a successful optical self-test.
Its HIDL transmit path logs a negative HAL result without returning that
result to the application's void `transmit()` call.
Consequently **a normal API return, this app's success result, and
`hasIrEmitter = true` are not proof of emitted IR** on this configuration.
That behavior was checked in AOSP source, not the GSI's exact framework
binary. Separately, the user reports actual TCL response through the API
adapter and IR Blaster on the tested image; those observations are useful
end-to-end evidence for those commands, but are not an optical waveform
measurement or a guarantee for other commands/devices.

## 3. App-specific integration context

The examined app already represents IR as frequency plus pulse durations,
but the phone's stock HAL path did not reach the HXD controller. The
ROM-side adapter now supplies a bounded standard-API path, so an
app-specific HXD backend is not required for the tested use case.

Existing integration points:

- [`IrTransmitter`](https://github.com/c6liu/android-ir-blaster/blob/master/android/app/src/main/kotlin/org/nslabs/irblaster/ir/IrTransmitter.kt)
  already accepts frequency in Hz and mark/space durations in microseconds.
- [`InternalIrTransmitter`](https://github.com/c6liu/android-ir-blaster/blob/master/android/app/src/main/kotlin/org/nslabs/irblaster/ir/InternalIrTransmitter.kt)
  currently wraps ConsumerIrManager.
- [`MainActivity`](https://github.com/c6liu/android-ir-blaster/blob/master/android/app/src/main/kotlin/org/nslabs/irblaster/MainActivity.kt)
  creates the internal backend, derives availability from `hasIrEmitter`,
  exposes carrier ranges, and dispatches all foreground transmit variants.
- [`AutomationTransmitter`](https://github.com/c6liu/android-ir-blaster/blob/master/android/app/src/main/kotlin/org/nslabs/irblaster/ir/AutomationTransmitter.kt)
  independently constructs the internal transmitter.
- [`IrButtonWidgetProvider`](https://github.com/c6liu/android-ir-blaster/blob/master/android/app/src/main/kotlin/org/nslabs/ir_blaster/IrButtonWidgetProvider.kt)
  also checks ConsumerIrManager availability.
- [`ir_transmitter_platform.dart`](https://github.com/c6liu/android-ir-blaster/blob/master/lib/utils/ir_transmitter_platform.dart)
  defines transmitter selection and capability data.

A backend must cover foreground buttons, raw/cycle input, automation,
widgets, device controls, and quick-settings use, not just one activity
call. If represented as a new selectable transmitter, its wire values,
saved settings, UI, and capabilities also need updates. Prefer a shared
internal-backend factory if it is exposed as device-specific Internal IR.

Existing USB formatters were checked for reuse. Their ElkSmart bulk and
legacy `ST`/`EN` packet formats do not match the HXD `/dev/ctrl` framing;
they cannot be reused as-is.

### The access problem

The live vendor policy explicitly permits `ctrl_device` reads/writes/opens
for `system_app_31_0`, `untrusted_app_25_31_0`, and
`untrusted_app_27_31_0`. The live mapping resolves the last attribute to
`untrusted_app_27`. This aligns with HxdIR's target SDK 27.

The app [targets SDK 36](https://github.com/c6liu/android-ir-blaster/blob/master/android/app/build.gradle).
The inspected vendor policy does not grant the corresponding modern-app
domain the same explicit access. Other effective grants would need checking
before claiming a definitive denial, but **HxdIR's working access cannot be
assumed to carry over**. Mode `0666` does not override SELinux.

JNI, Kotlin file I/O, and `TRANSMIT_IR` permission do not bypass that policy.
Do not lower target SDK, disable SELinux, change device permissions globally,
or depend on root as the compatibility solution.

These observations explain why direct app access was not chosen. Do not
ship the proprietary APK/native database as a substitute for the ROM adapter.
