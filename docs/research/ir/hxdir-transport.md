# What HxdIR does: transport and packets

## Transport

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

## Packet generation

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
  `q` for every entry is incorrect. The [detailed rules](codec-normalization.md) establish a
  16-to-1 quantization of M708 working values, but not their physical time
  scale.
- `getfigure` analyzes the normalized sequence and updates metadata/flags in
  the working structure after comparing candidate sequence regions. This
  appears to identify repeated/segment structure, but is not enough to assign
  the resulting flags a complete hardware repeat meaning. It is record
  normalization, not evidence that the final driver supports Android's full
  waveform or repeat semantics.
