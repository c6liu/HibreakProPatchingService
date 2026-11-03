# HiBreak Pro IR compatibility investigation

Investigation performed on 2026-11-03. **The device investigation was
read-only: no ROM implementation or device configuration changes,
installations, app launches, or IR transmissions.**

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

The second diagram's module implementation was inspected in the existing
stock-vendor backup, not read directly from the running HAL: SELinux denied
ADB access to the live library. The running service identity and reported
frequency table agree with that backup. This is strong evidence of an
interface mismatch, **not an end-to-end transmission test**.

**Recommended direction:** implement a ROM-side Android IR HAL adapter that
converts standard frequency/pulse-pattern requests to HXD packets and uses
the existing `/dev/ctrl` driver. That would benefit this app and other
ConsumerIrManager applications without device-specific integrations.

An app-specific backend is also plausible, but needs both an independent
HXD waveform encoder and a supported access path for modern apps. It is not
just a replacement of `ConsumerIrManager.transmit()` with a file write.

No new kernel driver appears necessary for the existing HxdIR path.
Static analysis can recover the app-side record transformations without IR
measurement equipment. General arbitrary-waveform compatibility remains
conditional on mapping those records to Android timings and carriers;
measurement is needed to validate physical output, not to continue APK
analysis.

## Inputs and limits

- Supplied APK: `HxdIR.apk` (analysis input; not copied into this repository).
- Package: `ht.song.remotestar.hxd`.
- Version: `88.17.101`, version code `8817101`.
- Minimum SDK: 18; target SDK: **27**; compile SDK: 30.
- APK SHA-256:
  `02217864bc97f74eb9c2c946f09aaa29e8aa08b9f330d48f8976fc58ac35e770`.
- Current app source revision:
  `c2fbf7887d594fd795393d0d7847771bc9ab9b2f`.
- Local [HibreakProPatchingService](https://github.com/c6liu/HibreakProPatchingService)
  checkout revision: `da5ce3c321553adf91d98e49471139e31a5e54ee`;
  its worktree was clean when inspected.
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

## 1. What HxdIR actually does

### Transport

`ActivityMain` selects `ETIO` for its `"io"` mode and as a fallback. Other
branches handle USB, network, and audio accessories; these are not evidence
that the phone's emitter is a USB device.

`ETIO` implements the application's transport interface using four JNI
entry points: `IOOpen`, `IOClose`, `IORead`, and `IOWrite`.
Its Java `ioctl` method is a no-op.

Disassembly of `libet_jni_io.so` establishes:

| Operation | Behavior |
| --- | --- |
| Open | Try `/dev/hxd_irda`, then `/dev/ctrl`, then `/dev/irremote`, each with `O_RDWR` |
| Write | Pass the byte buffer and requested length directly to POSIX `write()` |
| Read | Pass the buffer and length to POSIX `read()` |
| Close | Close the stored descriptor |

There is no ConsumerIrManager transmit call in the inspected APK bytecode.
The only ConsumerIrManager class reference found was AndroidX's generic
service-name map. The manifest does not request `TRANSMIT_IR`.
An activity-level `sharedUserId` attribute is not a manifest-level shared
UID declaration and does not establish that this app runs as system UID.

On the device:

- `/dev/ctrl` exists, is a character device, and has mode `0666`.
- Its SELinux label is `u:object_r:ctrl_device:s0`.
- `/sys/devices/platform/hxd019_ir/driver` points to the platform `ctrl`
  driver; that driver's binding points back to `hxd019_ir`.
- `/dev/hxd_irda` and `/dev/irremote` were not found.
- The stock kernel contains HXD019D driver diagnostics and GPIO
  open/read/write/acknowledgment/learning routines.

The APK's transport is therefore a byte-command interface to an existing
kernel-controlled IR chip, not Android's frequency-plus-microseconds API.

### Packet generation

The TV button path obtains `GetKeyValueEx` or `GetKeyValue`, then writes the
returned byte array through the selected transport. Learned codes go through
`ETIR.StudyKeyCode`; database codes also use `ETIR.SearchKeyData` and
device-specific processing, including toggle-bit handling.

The APK's `libet_jni_ir_tools.so` is about 106 MB uncompressed and contains
large device-code tables as well as conversion routines. Its bundled native
libraries are **32-bit ARM only** (`lib/armeabi`).
The phone supports 32-bit ARM as well as arm64, but copying that library into
an arm64 process would not work.

Confirmed static framing details:

| Path | Observed representation |
| --- | --- |
| Short learned input | `StudyKeyCode` accepts 110 bytes and returns 112 bytes through `send_remote_study_data`; framing starts with `30 02` |
| Extended learned input | Accepts 230 bytes and returns 232 bytes: `30 03`, input bytes 1 through 229 after native normalization, then an additive low-eight-bit checksum |
| Short checksum | The helper writes the additive checksum to output offset 111 |

The short helper calls a conversion routine and toggles a bit before
assembling the packet. It must not be treated as simply adding a header to
an arbitrary array of microsecond durations.

Further static analysis of `classes.dex` and the ARM native library found:

- The relevant JNI methods are `StudyKeyCode(byte[], int): byte[]` and
  `SearchKeyData(int, int, int): byte[]`. The library has no encoder entry
  point accepting carrier frequency plus a duration array.
- `ETDevice.Study(byte[])` delegates to `StudyKeyCode`. Ordinary key paths
  retrieve byte-array values from `ETKey` and choose the learned-code or
  database processing path according to key state. Device-family lookup
  wrappers call `SearchKeyData` with integer selectors.
- For the 110-byte learned form, native code widens the record into working
  values, normalizes it through `compdata` and its waveform helpers, then
  emits 109 payload bytes in a 112-byte `30 02` frame. `send_remote_study_data`
  seeds the additive checksum with `0x32`, adds the payload modulo 256, and
  stores the result at output byte 111. This path also mutates a stateful
  toggle bit before assembly.
- For the 230-byte form, native code normalizes the record and copies bytes 1
  through 229 into a 232-byte `30 03` frame. Its checksum accumulation starts
  at `0x33` and includes those 229 bytes.
- The normalizers inspect high-bit-marked values, combine adjacent bytes in
  some cases, and rescale/adjust values. This confirms a packed, proprietary
  record format; it does not yet identify a microsecond conversion or carrier
  mapping.
- In the 110-byte path, `get_remote_study_data` widens all 110 input
  bytes into 32-bit working entries, calls `compdata`, then copies working
  entries 1 through 109 back to input offsets 0 through 108 on success.
  Entry 0 is a discriminator that must be zero. `compdata` selects
  `Modifywave` followed by `delfeng` when entry 1 is at least `0x80`;
  otherwise it selects `modifywavem708`. This is a **record-flag dispatch,
  not a sequence-length dispatch**. Both routes use the same 110-byte input
  container, and neither is the separate 230-byte JNI route.
- The working entries use a continuation convention: values with bit 7 set
  (except the `0xF0` family) contribute their low seven bits as the high part
  and consume the following entry as the low byte. `modifywavem708` treats a
  `0xF0`-family entry as a longer form:

  ```text
  b < 0x80:                  x = b
  0x80 <= b < 0xF0:         x = ((b & 0x7F) << 8) | next
  0xF0 <= b <= 0xFF:        x = ((b & 0x0F) << 16) | (next << 8) | next2
  ```

  It first converts `x` to `q = (x + 2) >> 4`, then applies alternating
  corrections before re-encoding. In particular, an odd-position result
  subtracts the preceding adjusted even-position value; directly encoding
  `q` for every entry is incorrect. The detailed rules below establish a
  16-to-1 quantization of M708 working values, but not their physical time
  scale.
- `getfigure` analyzes the normalized sequence and updates metadata/flags in
  the working structure after comparing candidate sequence regions. This
  appears to identify repeated/segment structure, but is not enough to assign
  the resulting flags a complete hardware repeat meaning. It is record
  normalization, not evidence that the final driver supports Android's full
  waveform or repeat semantics.

### Recovered normalization rules and offline verification

The following uses zero-based working-entry indices, **not packet byte
offsets**. The stream starts at entry 5. Before normalization, entry 2 limits
the number of decoded stream values; the separate length argument bounds
the packed working entries.

| Working entry | Proven use |
| --- | --- |
| 0 | Format discriminator; these helpers require zero |
| 1 | Flags; values at least `0x80` select `Modifywave` plus `delfeng` |
| 2 | Decoded-value count on input; replaced by a segment count by `getfigure` |
| 3 | Another segment count written by `getfigure` |
| 4 | Not assigned a meaning by this analysis |
| 5 onward | Packed value stream, decoded independently of the header |

#### M708 route

At `0x5576` through `0x55a0`, let `i` be the decoded stream position,
`x` its unpacked nonnegative value, and `q = floor((x + 2) / 16)`:

```text
even i: t = q - (1 if x > 4093 else 0)
        reject with status 1 if t > 128
odd i:  t = max(1, q - previous_adjusted_even_value - 2)
```

The `4093` branch is present in the binary, but such an even input is
already too large to pass the `t <= 128` check. The largest accepted even
input is 2061 working units; 2062 is rejected. These are **not microseconds**.
Odd inputs can use the three-entry `0xF` form, including a nonzero high nibble
payload; their conversion is not just an independent interval rescale.

For nonnegative `t`, the output uses one entry below 128 or
`[0x80 | (t >> 8), t & 0xFF]` otherwise. After the stream loop, the routine
changes the first pair again:

- First even value: a one-entry form is reduced by 3, with a minimum of 1;
  a two-entry form is reduced by 5, with low-byte borrow.
- First odd value: a one-entry form is increased by 3, capped at 127;
  a two-entry form is increased by 4, with low-byte carry.

Even/odd is proven; identifying these positions as optical marks/spaces
and identifying the odd input as a cumulative pair measurement remain
interpretations, not measured hardware facts.

#### `Modifywave` and `delfeng` route

`Modifywave` decodes one-entry or high-bit-marked two-entry values. It does
**not** recognize the M708 three-entry form and does **not** divide by 16.
For decoded nonnegative `x`, its main loop applies:

```text
even i: t = x - 7 if x > 7 else 2
odd i:  t = x + 3
```

It then applies first-pair adjustments: the single-entry first even value
increases by 2, capped at 127; the two-entry form increases by 3 with carry.
The two-entry first odd value decreases by 1 with borrow; a single-entry
first odd value is only forced to 2 when it is at most 1.

`delfeng` follows this transformation and has a rewrite branch for an odd
decoded value at most 4. Do not assume it simply merges two neighboring
marks: an isolated run on `[20, 3, 30, 40]` rewrites the stream prefix to
`[26, 3, 30, 40]`, not `[53, 40]`. Further tracing is needed before assigning
this branch a deglitching meaning or copying it into a new encoder.

#### Segment metadata and status handling

`getfigure` first finds the maximum normalized stream value, then selects
up to three candidates at least `maximum - floor(maximum / 8)`. It compares
sequence regions and writes entry 1 as `(old_flags & 0x88) | classification`,
with classification values 0 through 3 on the examined branches. Entries 2
and 3 are selected segment counts rounded upward to even values. This is
much stronger evidence for segment/repeat classification than the function
name alone, but it still does not define the controller's repeat contract.

`compdata` decrements its length argument before dispatch. It calls
`delfeng` even if `Modifywave` returned failure, and only invokes `getfigure`
when the selected normalizer returned zero. It does not propagate
`getfigure`'s return value. `learn_data_in_out` likewise does not check the
return from `get_remote_study_data` before continuing. A new translation
layer must therefore implement its own explicit validation rather than
treating the APK's returned array length as proof of successful conversion.

#### Reproducible software checks

[`tools/verify-hxd-codec.py`](../tools/verify-hxd-codec.py) runs the original
Thumb instructions in Unicorn using synthetic records. It verifies the
library hash below, maps only the isolated helper code and private memory,
and does not execute JNI, transport routines, Android services, or device
access. The APK and its proprietary code tables are not included.

```sh
uv run --script tools/verify-hxd-codec.py /path/to/HxdIR.apk
```

The script declares its tested Unicorn dependency; this is investigation
tooling, not a ROM-build dependency. All 14 isolated-normalizer vectors passed,
covering continuation decoding, the three-entry form, alternating
corrections, first-pair corrections, the 127/128 output boundary, oversized
even-value rejection, and the observed `delfeng` rewrite. Representative
results below are decoded input values and packed output prefixes, in
decimal:

| Routine | Decoded input | Output prefix / status |
| --- | --- | --- |
| M708 | `[160, 640]` | `[7, 31]`, success |
| M708 | `[16, 16]` | `[1, 4]`, success |
| M708 | `[160, 65536]` | `[7, 143, 248]`, success |
| M708 | `[2045, 2560]` | `[124, 34]`, success |
| M708 | `[2046, 2560]` | `[128, 123, 33]`, success |
| M708 | `[2062, 2560]` | Status 1; no usable normalized output |
| `Modifywave` | `[20, 30, 40, 50]` | `[15, 33, 33, 53]`, success |
| `delfeng` alone | `[20, 3, 30, 40]` | `[26, 3, 30, 40]`; no status contract asserted |

These tests verify software behavior only, not the physical unit, carrier,
controller interpretation, or whole-JNI replay path.

### Extended-record and database packet construction

The 230-byte branch in `StudyKeyCode` is separate from `compdata`. An
isolated run from `0x2a24` to `0x2b70` reproduces its normalization and complete
232-byte packet, stopping before JNI allocation/copy callbacks. All 22
synthetic extended vectors match the independent model in
[`tools/verify-hxd-codec.py`](../tools/verify-hxd-codec.py) **byte-for-byte**,
including the checksum. These include fixed patterns, 16 deterministic
pseudorandom records, and controlled memory after the input.

The recovered operations use zero-based **input byte offsets**:

1. Scan bytes 37 through 226. Set the low nibble to `0xF` when bit 3 is
   set; otherwise replace a high-bit-set byte with `0xF0`.
2. Search for the first nine-byte all-zero window starting at offsets
   38 through 215, advancing by **one byte**, not by a record-block stride.
   At a match starting at `s`, OR byte `s - 1` with `0x0F` if its low
   nibble was zero, set byte `s` to `0xFF`, and stop searching. The last
   window ends at byte 223.
3. Scan bytes 37 through 226 again. Set the low nibble to `0xF` when bit
   3 is set, then replace any high-bit-set byte with `0xFF`.
4. If byte 8, interpreted as a signed byte, is at least 33, set byte 8
   to 1 and byte 7 to 21. Signed values at least 128 in the stored unsigned
   representation therefore do not take this branch.
5. Replace byte 2 with `0xFE` when its signed value is at most 3; replace
   byte 1 with `0xFE` when its signed value is at most 4.
6. Replace byte 4 with `0x34` only if it was zero.
7. Emit `30 03`, normalized input bytes 1 through 229, and the low eight
   bits of the sum of all preceding packet bytes.

The harness checks that every input read stays within the 230-byte record
on these vectors. Changing the mapped bytes after the input does not change
the tested tail case's output. These checks prevent mistaking the sliding
zero-window search for an out-of-bounds block-stride search.

The `0x34` default is a useful **candidate field**, not a proven frequency:
input byte 4 becomes packet byte 5, but this route does not perform a
frequency-to-period calculation or label the field as carrier. Do not infer
38 kHz, a timer clock, or a duration unit from this constant alone. Also,
the `0xFF` rewrites make this route unsuitable for inserting an arbitrary
duration byte stream without first understanding its bit-packed format.

`SearchKeyData` also has compact database-driven routes, not just learned
replay. The branches ending at `0x3ae0` construct ten-byte `30 00` packets:
seven selected database bytes become packet bytes 2 through 8, followed by
the additive checksum at byte 9. Different device families pick those
bytes from different record locations; this is not a generic waveform
interface. Four synthetic tests execute the assembly block at
`0x3800` through `0x3830` and verify the exact ten-byte result without
loading or copying a proprietary database record.

#### Variable-length `30 01` branch

The device-family selector `0xC000` branches at `0x36da` to `0x3c06`.
It accepts odd identifiers from `0xC001` through `0xC023` on the examined
path. The second JNI selector indexes `arc_table` at a stride of 6004 bytes;
for selector values above 511 the branch instead uses the local three-byte
fallback initialized to `[2, 0, 0]`. This is a database-family path, not a
duration-array API.

At `0x3c40` through `0x3ca2`, a selected record's first byte supplies a data
length `n`, and its following `n` bytes are copied without waveform
normalization. The resulting packet has `n + 18` bytes:

| Packet offset | Observed value |
| --- | --- |
| 0, 1 | `30 01` |
| 2, 3 | Identifier, high byte first |
| 4 through 14 | Eleven zero bytes |
| 15 | `(n + 1) & 0xFF` |
| 16 through `15 + n` | The `n` selected data bytes |
| `16 + n` | Suffix derived from saved value `K`: `(K + 95) & 0xFF` |
| `17 + n` | Native checksum described below |

The inspected caller initializes `K` to `0xA0`, giving suffix `0xFF`.
The assembly block itself has no frequency-to-period or
microseconds-to-ticks calculation. The identifier and copied database
content cannot yet be given a generic carrier/pulse interpretation.

**Checksum quirk:** the code writes the suffix at offset `16 + n`, but then
loads offset `15 + n` when completing the checksum. Thus it counts the last
data byte a second time, rather than including the suffix. If `n` is zero,
it counts the length byte (1) a second time instead:

```text
checksum = (0x31 + id_high + id_low + ((n + 1) & 0xFF)
            + sum(data) + (data[-1] if n > 0 else 1)) & 0xFF
```

Five synthetic vectors verify the complete assembly-block output, including
zero, one, three, 38, and 255 data bytes. A dedicated check establishes that
the one-byte case does **not** equal the ordinary sum of preceding packet
bytes. This is confirmed APK behavior, not a verified controller checksum
specification; a new encoder must not silently apply either checksum rule
across all packet families.

The harness intercepts only the known `memcpy` PLT entry for this block and
validates its source, destination, and length before performing a private
memory copy. It does not run database lookup or JNI callbacks. The 255-byte
test intentionally probes the isolated block's length-byte wrap; it does
**not** establish that a full JNI call or controller supports that size.
Other database branches also emit 12-byte `30 00` packets with an additional
selector byte at offset 10 and checksum at offset 11; the ten-byte form is
not universal.

Neither command byte `00` nor `01` can be substituted for the learned
`02`/`03` format based on header resemblance.

The exported `code_format` and `STandantdata` objects are referenced by
toggle detection/modification helpers. Their names and constants are not
enough to identify carrier encoding; the executable references must be
traced before assigning them timing or protocol-descriptor meanings.

**ROM-layer consequence:** choose a validated representation first, then
construct its fields explicitly. Reusing `StudyKeyCode` as a carrier-plus-
duration encoder would mix format-specific rewrites, sentinel handling,
and database replay without a proven mapping. The full hardware translation
is still unimplemented.

These call signatures and paths strengthen the conclusion that the APK is a
learned-code/database replay implementation, not a generic ConsumerIr timing
encoder. Static disassembly can continue to recover record structure and
conversion behavior without a meter. What remains unproven without optical
measurement is whether a reconstructed request produces the expected carrier
and pulse waveform at the emitter.

These details establish a credible **learned-code replay** path. They do
not establish a complete encoder from arbitrary Android pulse patterns.
Still unresolved:

- Mapping each record family's working units to real time, determining how
  to construct the M708 paired inputs, and mapping extended durations to
  controller fields. `Modifywave` does not use M708's divide-by-16 step.
- Carrier encoding, supported carriers, and duty-cycle behavior.
- Maximum waveform size and long-gap representation.
- Complete repeat, toggle, termination, and completion semantics.
- Whether all patterns this app supports fit either HXD representation.

The external [ESP8266 HXD019 driver](https://github.com/IoTServ/ESP8266_IRC/blob/master/driver_lib/hxd019.c)
independently documents extended learned replay with the same `30 03`
header, 229-byte payload, and checksum. It also cautions that HXD019
variants differ and reports that only its second learning method replayed
successfully. It is corroborating research, not a verified HiBreak driver
specification or permission to copy its code.

### Reproducible binary landmarks

Offsets below are ELF virtual addresses, with the Thumb-state bit removed:

Use the NDK's `llvm-objdump` with `--triple=thumbv7-linux-gnueabi` for these
Thumb helpers. In this library, default disassembly misinterprets the helper
instructions as ARM; disassemble the ARM `.plt` separately without that
Thumb override, and resolve its targets using ELF relocations.

| Binary | Functions / relevant offsets |
| --- | --- |
| `libet_jni_io.so` | `ctrl_open` `0x0ec4`, `ctrl_write` `0x0f10`, `ctrl_read` `0x0f28`, `ctrl_close` `0x0f40` |
| `libet_jni_ir_tools.so` | `StudyKeyCode` `0x29e8`, `SearchKeyData` `0x33d0`, `get_remote_study_data` `0x3f98`, `send_remote_study_data` `0x400c`, `compdata` `0x40e0`, `Modifywave` `0x52bc`, `delfeng` `0x53d8`, `modifywavem708` `0x5508`, `getfigure` `0x565c` |
| Stock arm64 `consumerir.common.so` | LIRC open at `0x12fc`, carrier ioctl at `0x1348`, duty-cycle ioctl at `0x1380`, pulse-buffer write at `0x13e0` |

SHA-256 of the inspected libraries:

```text
ed796b13c77785b4f95b5992cb9ac7394da79430e9de62bc2762f1e4a424c7a0  libet_jni_io.so
513b6dd35a2f0b8cef6d3906341587c4586a3178539150d7bd26552db1c2aceb  libet_jni_ir_tools.so
5aad71b23fb75cad6de0cd95b2a0810b13d13a75f7dd08a97254a40057e3e588  stock consumerir.common.so
```

## 2. Why Android advertises IR anyway

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
binary.

## 3. Can this app implement HxdIR's protocol?

**Plausible, with additional codec and access work.**

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

Possible access designs are a permission-protected ROM broker or carefully
scoped ROM policy/integration. A broker should accept validated waveform
requests, not arbitrary device paths or unrestricted vendor packets.
An independent native encoder can support arm64 and 32-bit without shipping
the proprietary APK, SDK library, or remote-code database.

## 4. Can the custom ROM expose standard Android IR?

**Yes as an architectural approach; waveform coverage needs validation.**
This is a HAL translation task, not a new appliance protocol. Android IR
defines carrier frequency and pulse timing, not NEC/RC5/etc. encoding.

The patching project's [build guide](BUILDING.md)
preserves stock vendor and patches an ext4 system/GSI image. Its current
display patcher does not add an IR HAL or new SELinux policy; it relies on
the existing `phhsu_daemon` domain for its display daemon.
Adding a HAL is therefore additional ROM integration, not a switch in the
current display service.

Two routes:

| Route | Benefit | Required integration |
| --- | --- | --- |
| Replace the legacy Consumer IR module with an HXD adapter | Reuses the running HIDL service and framework plumbing | Correct module selection/ABI, offline vendor change or verified library overlay, and HAL access to `ctrl_device` |
| Add an AIDL `android.hardware.ir.IConsumerIr/default` adapter | Modern interface; AOSP Android 16 prefers declared AIDL IR over HIDL | Native service, build/install rules, init lifecycle, correctly scoped VINTF declaration, service labeling and SELinux policy; verify discovery and startup on the actual GSI |

A system-image-only AIDL approach is attractive for this patching project,
but is not assumed to work by merely copying a binary/XML file into the
image. Its declaration location, SELinux policy composition, and service
selection must be proven against the target GSI.

The observed `hal_ir_default` vendor policy explicitly grants `irtx_device`
access but has no explicit grant to `ctrl_device`. Replacing only the
transmit function can therefore leave an access failure. Do not repurpose
the display daemon's domain as an IR HAL without checking all required
device, Binder, and service-registration permissions.

The adapter must:

1. Validate frequency and positive durations, with overflow-safe size/time
   limits; Android documents a two-second transmission limit.
2. Encode supported patterns into the HXD format, rejecting patterns that
   cannot be represented rather than truncating or silently approximating.
3. Serialize requests and learning/replay ownership.
4. Handle device open, full packet writes, acknowledgment/completion,
   timeout, and close correctly; avoid automatic retransmission after an
   ambiguous failure.
5. Report only verified carrier ranges, not the generic stock table.
6. Preserve synchronous Android transmission semantics.
7. Surface hardware failures through HAL status and diagnostics; account
   for framework versions that do not propagate all failures to callers.

Do **not** symlink `/dev/lirc0` to `/dev/ctrl`. The ioctl contract and byte
payloads differ. A LIRC-compatible kernel frontend is an alternative, but
is more invasive and still needs the same HXD waveform translation.

IR learning is a separate optional feature. ConsumerIrManager exposes
transmission, not reception; adding a standard transmit HAL would not
automatically expose HxdIR's learning UI.

## 5. Recommended next investigation

1. Trace the contents/consumers of `30 01`'s copied data and references to
   candidate carrier fields, including the extended route's byte-4 default
   `0x34`, and locate the source of M708 paired timing values. The
   variable-length branch's packet layout and native checksum are now
   verified, but their controller meanings are not.
   `Modifywave`/`delfeng` are selected by flags in the 110-byte route, not by
   a long-waveform length. Compare representative records with known
   protocol encodings without redistributing proprietary code tables.
2. Extend the native vectors to segment classification and complete
   short-record conversion. The current harness verifies 14 isolated
   normalizer vectors, 22 extended packets, four compact database packets,
   and five identifier packets, not full JNI or hardware semantics.
   Do not open the IR
   device or transmit during codec analysis.
3. If measurement equipment becomes available, observe one known-working
   command's optical waveform to validate the inferred carrier, pulse units,
   and repeat behavior. That is physical validation, not a prerequisite for
   static analysis.
4. Establish permission-protected access on the target ROM. Test from this
   app's actual target-SDK-36 domain, not only from root/ADB.
5. Specify which Android waveforms the recovered HXD format can represent;
   reject unsupported patterns rather than silently approximating them.
   Do not redistribute proprietary code tables.
6. Build a minimal native encoder/transport proof, followed by the chosen
   HAL or app-backend integration.

Acceptance criteria before calling it standard-IR compatible:

- Matching carrier, pulse timing, payload, and repeat behavior for captured
  reference commands; report measured errors against the reference.
- Successful appliance response and independently observed optical output,
  not just Binder success.
- NEC-style patterns plus biphase protocols, odd-length trailing marks,
  long gaps, and longer air-conditioner frames where supported.
- Defined frequency/timing/buffer limits, with explicit rejection outside
  those limits and no partial command emitted on preflight failure.
- Concurrent requests, busy device, failed writes, unsupported input, and
  timeout behavior.
- Cold boot and SELinux-enforcing operation without root for callers.
- For a ROM HAL: this app and a second ordinary ConsumerIrManager client.
  For an app backend: every foreground and background transmit surface.

**Decision:** favor ROM-side HAL translation for ecosystem compatibility;
use an app backend only if app-local support is the priority and a sound
modern-app access mechanism is available. Neither implementation is
considered proven until the remaining waveform tests pass.

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
