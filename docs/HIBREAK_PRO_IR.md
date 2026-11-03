# HiBreak Pro IR compatibility investigation

Initial investigation performed on 2026-11-03. **The initial inspection was
read-only: no ROM implementation or device configuration changes,
installations, app launches, or IR transmissions.**
Later, explicitly authorized ROM builds and device tests established
optical transmission and working TCL Volume Up control through the v6
diagnostic app. The v7 build adds an opt-in, experimental
[NEC-only standard Android adapter](#experimental-standard-android-nec-adapter-v7);
the user subsequently reported that the standard-client test works.
The v8 follow-up adds the app's nominal 38222 Hz NEC carrier as an explicit
alias of the same controller-built NEC output; see the compatibility note below.

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

**Recommended direction:** a ROM-side Android IR HAL adapter that
converts standard frequency/pulse-pattern requests to HXD packets and uses
the existing `/dev/ctrl` driver. That would benefit this app and other
ConsumerIrManager applications without device-specific integrations.
The experimental v7 implementation takes the bounded NEC/NECext route,
not the still-unresolved generic arbitrary-waveform route.

An app-specific backend is also plausible, but needs both an independent
HXD waveform encoder and a supported access path for modern apps. It is not
just a replacement of `ConsumerIrManager.transmit()` with a file write.

No new kernel driver appears necessary for the existing HxdIR path.
Static analysis can recover the app-side record transformations without IR
measurement equipment. General arbitrary-waveform compatibility remains
conditional on mapping those records to Android timings and carriers;
measurement is needed to validate physical output, not to continue APK
analysis.

The recovered stock kernel now confirms a bit-banged controller transport:
its ioctls drive individual GPIOs, and its initialization sends no
carrier/timer configuration packet. It does not expose a hidden generic
IR timing API. See [the stock driver trace](#5-stock-firmware-driver-discovery)
for the exact read commands, byte limit, and error semantics.

A subsequent stock-resource search found no HXD firmware/update candidate
in the inspected OS resources. Public manufacturer documentation does
identify a **conditional alternative**: `30 30 60` enters an SCL-controlled
IR-envelope mode on newer chips. Current E-family marketing also advertises
custom encoding, but does not tie that claim to this command or phone.
The inspected documentation does not specify carrier selection,
mode exit, or HiBreak variant support, so this is not yet a working generic
HAL. See [the resource and public-source comparison](#6-stock-resources-and-public-hxd019-comparison).

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

#### Repeat investigation: host resends versus encoded segments

Follow-up tracing compared the supplied APK, the public Wi-Fi APK, and the
CRC-verified complete native/DEX members of the truncated HXD4816 APK.
There are **two separate repeat mechanisms**, not one inferred repeat byte:

1. **Host long-press resending is established.** `FragmentTV.onLongClick`
   sets `mLongKey` for selected keys and posts its runnable. In all three
   versions, `FragmentTV$5.run` obtains `GetKeyValue(mLongKey)`, calls one
   `ITg.write`, then posts itself with a **300 ms delay after the write**.
   This is not a guaranteed 300 ms optical frame period: write duration
   and Android scheduling add to the interval. `onTouch` handles release
   by clearing `mLongKey` and removing callbacks; the inspected release
   path sends no controller stop packet. Normal `onClick` sends one packet.
2. **Native segment classification is established, but the controller's
   expansion is not.** `getfigure` detects large intervals and compares
   candidate regions, then stores a classification and two counts/boundaries.
   It does not emit repeated writes or specify an Android repeat count.

The host resend regenerates the selected key, not necessarily identical
cached bytes. `ETDevice.GetKeyValue` invokes `Study` for learned keys and
`Work` for database keys; `Study` calls the stateful native converter.
Consequently, a learned short key can take the automatic toggle path on
each host resend. A new generic transmitter should not copy this UI behavior
as its own protocol repeat/toggle policy.

Additional emulator tests execute the original `getfigure` at `0x565c`
directly on synthetic normalized streams. Let
`A = [10,20,10,30,10,20,10,100]` and
`B = [50,60,50,60,50,60,50,100]`. The large value 100 is a separator
candidate; these are synthetic units, not calibrated pulse durations.
With input flags zero, the results are:

| Input stream | Classification (working entry 1) | Entry 2 | Entry 3 |
| --- | --- | --- | --- |
| A | 1 | 8 | 8 |
| A+A | 1 | 8 | 8 |
| A+A+A | 1 | 8 | 8 |
| A+B+A | 3 | 8 | 16 |
| A+B+B | 2 | 8 | 16 |
| `[10,20,10,30,10,100,10,100,10,100]` | 2 | 6 | 8 |

These vectors distinguish same-frame, alternating-frame and different-tail
structures in the software classifier. Crucially, one, two, and three
copies of A all yield `1,8,8`: **the metadata is not the number of copies
captured or the number of transmissions to request**. Entries 2/3 are
decoded stream positions/counts, not necessarily packed-byte offsets.
Input flags `0x80` and `0x88` preserve those bits and produce the same
classifications. For these small-separator vectors, input flag `0x40`
instead produces classification zero and both counts equal the whole
stream length. This is branch-specific evidence, not proof that `0x40`
universally means "send once." All **24** combinations are regression
tests in the codec harness.

`GetAirDelay` is another separate mechanism: it retrieves a database
integer which the air-conditioner wizard passes to `Thread.sleep`.
That is host pacing in milliseconds, not a carrier calculation or a
generic protocol repeat period.

Still unknown: how many optical frames a single `30 02`/`30 03` command
emits for each classification, precise frame/gap timing, the controller's
busy/completion contract, and whether a database command synthesizes
protocol-specific repeat frames internally. APK host resends and the
camera test do not answer these questions.

#### Carrier investigation across three codec versions

Native code comparison located `StudyKeyCode` at `0x29e8` in the supplied
and Wi-Fi versions and `0x29dc` in HXD4816. The native database builders
and segment classifiers differ in size/address, so version identity
must not be assumed merely because the JNI names match.

Code-only emulation swept **all 256 values** of input byte 4 through the
extended normalization block in each version (**768 probes**):

- Zero becomes decimal 52 (`0x34`).
- Every value 1 through 255 is preserved exactly.
- There is no frequency-range check or Hz-to-period calculation on that
  field in these paths. All three have the same transfer function.

The main codec harness additionally checks all 256 field values through
the original short-record normalization/packet helpers: **even zero passes
unchanged** there. Extended and short paths therefore differ in defaulting;
the extended zero-to-`0x34` repair must not be generalized to all packets.
The extended packet sweep also checks complete packet/checksum output.

This narrows where a carrier mapping would have to live: either the
controller interprets an already-encoded field, or carrier selection is
implicit in a database/protocol format. The inspected host conversion
does not supply the missing mapping. It still does **not** prove byte 4
is a carrier field, or that `0x34` means 38 kHz. A proposed relation such
as `2 MHz / 52 ~= 38.46 kHz` can fit a common frequency by choosing a
clock, but no recovered clock/divider definition justifies that formula.
Do not expose a fabricated frequency range in an Android HAL.

**Current implementation consequence:** bounded HXD/database transmission
is demonstrated; host-request repetition can be implemented explicitly.
Generic frequency-controlled waveform transmission remains blocked on a
carrier definition and per-command optical-repeat semantics, not on
SELinux access. A known protocol command that actually operates an
appliance can constrain these hypotheses; camera brightness alone cannot
measure carrier frequency or determine frames per command.

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
library hash below. Isolated tests map selected helper code; complete
short-record tests additionally map the local ELF load segments and resolve
its internal references. Database/descriptor bytes stay in emulator memory,
not in the repository. No JNI callbacks, transport routines, Android
services, or device access execute. The APK and its proprietary code tables
are not included.

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
controller interpretation, or whole-JNI replay path. The whole-record
checks below extend coverage beyond the isolated normalizers.

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
traced before assigning them carrier meanings. The toggle-descriptor
correlation below narrows their timing interpretation.

**ROM-layer consequence:** choose a validated representation first, then
construct its fields explicitly. Reusing `StudyKeyCode` as a carrier-plus-
duration encoder would mix format-specific rewrites, sentinel handling,
and database replay without a proven mapping. The full hardware translation
is still unimplemented.

### Learned-data ingestion: where the numbers originate

DEX tracing of `ActivityMain$StudyTask.doInBackground` establishes:

- Learning selections `"0"`/`"99"` allocate 110 bytes and issue the
  three-byte command `30 10 40`. Selections `"1"`/`"100"` allocate 230
  bytes and issue `30 20 50`. These are learning commands, not transmit
  waveform headers.
- The task sends that command through `ITg.write`, waits 200 ms, clears the
  buffer, and calls `ITg.read(buffer, buffer.length)`.
- A positive read result hands off the buffer without checking that the
  entire requested length arrived. Normal selections send handler message
  5; selections 99/100 broadcast the hexadecimal buffer directly.
- `ActivityMain$12.handleMessage` gives the same buffer to the replay
  preview callback and the confirmation callback. Preview calls
  `StudyKeyCode`; confirmation hex-encodes the original buffer and
  broadcasts it for learned-key storage. It does not first construct
  Android-style pulse durations.
- `ETIO.read` delegates to JNI `IORead`. At `libet_jni_io.so:0x0e74`,
  JNI obtains the byte-array storage, calls `ctrl_read`, releases the array
  with copy-back enabled, and returns the read result. `ctrl_read` at
  `0x0f28` passes the existing descriptor, destination, and length to
  `read`; it contains no timing arithmetic or carrier conversion.

Consequently, M708's paired values already arrive from the `/dev/ctrl`
boundary on this transport. Their producer is in the driver/controller
path, not in this APK's Java learning logic. APK normalization and
descriptors can constrain their meaning but cannot expose a timer
initialization that is absent from the APK. Driver disassembly/source or
an independently calibrated format reference is the next offline source
for an exact clock. No physical measurement is required to examine those.

The positive-read-only check also means saved zero-padded records are not
proof that a complete learned waveform was received. A new ROM service
must validate lengths and record structure independently.

### Complete short-record emulation

The harness now executes `get_remote_study_data -> compdata -> normalizer
-> getfigure`, then `send_remote_study_data -> keytogglebit`, including
native toggle classification. Two synthetic records cover the M708 and
high-flag `Modifywave` routes. It checks all 110 caller-buffer bytes after
normalization and all 112 packet bytes for three consecutive sends.
The first and third packets match; the second differs in the tested
toggle flag and its checksum.

Additional assertions verify:

- Changing input byte 4 to 36, 38, 52, or 56 preserves that byte as
  normalized byte 3 and packet byte 5. There is no frequency conversion
  in this path. These test numbers are not claimed to be valid hardware
  frequency encodings.
- A nonzero discriminator and an oversized M708 even value cause
  `get_remote_study_data` to return zero and leave the caller's record
  unchanged. Internal working storage can already have been modified.
- A synthetic accepting record runs through the complete
  `learn_data_in_out` wrapper, including normalization, framing, and its
  post-conversion validity checks. The complete result matches an expected
  112-byte packet. A zero-byte-1 input takes the wrapper's rejection path.
- `learn_data_in_out` returns zero for both the accepted and rejected
  cases. Its return code is therefore not a usable success discriminator;
  inspecting and validating its output is essential.

The full-record emulator allows only the required internal helper calls,
private-memory copy/clear operations, and a recorded no-output Android log
stub. Unexpected external calls fail explicitly. No file, device, timing,
or networking imports are enabled, and instruction budgets must complete
at the designated return address. The local ELF mapping is about 106 MB.
This tests native helper behavior, not an Android dynamic linker or JNI VM.

The fixed payload also retains unused working bytes: in one synthetic
M708 case, packed source bytes remain beyond the normalized sequence.
The checksum includes all 109 emitted payload bytes, not just the decoded
duration count. Do not equate unused bytes with newly zero-initialized
output or derive a variable packet length from the sequence count.

### Known-protocol correlation: useful evidence, not a clock calibration

The executable stride at `JudgeToggleBit:0x4290` is 87 bytes, and the
696-byte `code_format` object therefore contains eight descriptors.
The native loop returns `8 - descriptor_index` for a match, or zero when
none matches. The descriptors are used for toggle waveform
classification, not for translating a frequency argument.

The harness synthesizes public protocol shapes rather than copying a
proprietary remote-control entry:

- [RC-5](https://www.sbprojects.net/knowledge/ir/rc5.php): a 14-bit
  Manchester frame with 889-us half-bits, start bits set, toggle clear,
  address zero, and command zero; adjacent equal levels are merged.
  The leading idle half-bit and any trailing idle half-bit are omitted.
- [NEC](https://www.sbprojects.net/knowledge/ir/nec.php): a 9000/4500-us
  leader followed by address/command zero and their inverse bytes,
  approximately 560-us marks, 565/1690-us spaces, and a trailing mark.
  This is a timing-shape probe, not a claim of exact appliance tolerances.

Each shape is scaled into hypothetical normalized working units and fed
directly to `JudgeToggleBit`, not to an emitter:

| Hypothesized microseconds per normalized unit | RC-5 toggle result | NEC toggle result |
| --- | --- | --- |
| 1, 2, 4, 8, 14 | 0 | 0 |
| 16 | 2 (descriptor index 6) | 0 |
| 18 | 2 (descriptor index 6) | 0 |
| 20, 22, 32, 64 | 0 | 0 |

All 22 classifier probes are reproducible in the harness. They give a
**plausible approximately 16-us normalized timing scale**, but 18 us also
matches: this is a tolerance-based recognizer, not a unique calibration.
If the normalized scale were exactly 16 us, M708's divide-by-16 stage
would suggest approximately 1 us per raw unit; that remains a hypothesis.

An additional synthetic RC-5 replay test feeds the 16-us hypothesis's
normalized values to `send_remote_study_data`. The first and third packets
match, while the second changes **waveform bytes**, not only the header
flag; all three additive checksums pass. This executes the native
`JudgeToggleBit` and `changetogglebit` paths. It verifies software toggle
behavior, not a received optical RC-5 command.

Android's caller already supplies the waveform it wants transmitted.
Automatic protocol detection and waveform toggle mutation are therefore
another reason not to reuse this APK replay routine unmodified as the HAL
encoder. Toggle semantics belong to the caller's encoded waveform, not to
an inferred appliance protocol inside a generic translation service.

NEC's zero result does not mean NEC is unsupported: this function detects
toggle formats, while ordinary NEC has no RC-5-style toggle bit. Some
unscaled NEC probes exceed the 110-entry learned container and are
intentionally run only in a larger private diagnostic buffer. They do
not establish whole-record capacity.

RC-5's documented 36-kHz carrier and NEC's 38-kHz carrier are independent
reference facts. Classifying their envelope shapes does not prove which
record byte encodes those carriers. The preserved `0x34` field must not
be called a 38-kHz divider solely because the timing hypothesis fits.

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

The external [ESP8266 HXD019 driver](https://github.com/IoTServ/ESP8266_IRC/blob/0c27db989c17b9964c0669fb0037f834d3a33eaa/driver_lib/hxd019.c)
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

## 5. Stock firmware driver discovery

The supplied local stock backup contains an Android boot-v2 image with a
gzip-compressed ARM64 kernel in `boot_a.bin`. Read-only extraction and
decompression recovered Linux 4.19.191; `vmlinux-to-elf` recovered 170560
kernel symbols from its embedded kallsyms tables. The reconstruction
guessed base address `0xffffff8008080000`; the following addresses belong
to that reconstruction, not runtime KASLR addresses.

The kernel contains HXD019 driver diagnostics and the corresponding
executable functions:

| Symbol | Reconstructed virtual address |
| --- | --- |
| `ctrl_read` | `0xffffff8008c56a08` |
| `ctrl_write` | `0xffffff8008c56fd4` |
| `ctrl_ioctl` | `0xffffff8008c574dc` |
| `ctrl_open` | `0xffffff8008c57608` |
| `gpio_start` | `0xffffff8008c577e8` |
| `gpio_write_data` | `0xffffff8008c57964` |
| `gpio_read_data` | `0xffffff8008c57a78` |
| `gpio_stop` | `0xffffff8008c57b88` |
| `gpio_learn` | `0xffffff8008c57ff4` |
| `gpio_init` | `0xffffff8008c57ce0` |
| `_ctrl_probe` | `0xffffff8008c5836c` |
| `ctrl_init` | `0xffffff8009cf88f0` |

### Wiring and initialization

The extracted `dtb` has an Android DT-table wrapper; its single FDT starts
at offset `0x40`. The enabled `/hxd019_ir` node has compatible
`mediatek,ctrl` and these GPIO properties:

| Property | MT6877 pin-controller offset | Flags |
| --- | --- | --- |
| `gpio-i2c-scl` | 104 | 0 |
| `gpio-i2c-sda` | 105 | 0 |
| `gpio-ir-state` | 106 | 0 |
| `gpio-ir-en` | 190 | 0 |

These are offsets within the `/pinctrl` GPIO controller, not an assumption
about global Linux GPIO numbering. The probe resolves these properties
and drives IR enable high. `ctrl_init` registers the platform driver and
character device, allocates shared private storage, creates the device,
and calls `gpio_init`. That helper sets state input, SDA high, SCL high,
then SCL input. Neither initialization path uploads firmware or sends a
carrier/timer configuration packet. `ctrl_open` only associates the shared
private storage with the file; release and platform removal return zero.
The separate `gpio_learn` helper sends the already known `30 10 40`
learning command, not a new timer setup command.

### Write contract and acknowledgments

`ctrl_write` clamps the requested count to **255 bytes** and copies that
many user bytes into its private buffer. It recognizes `30 10 40` and
`30 20 50`, setting global `isOne` to zero or one respectively. It also
calls `gpio_read_data` once before the copy/setup sequence and logs the
result; this byte does not become an application response.

After handshake/setup, the loop at `0xffffff8008c57390` loads successive
buffer bytes and passes each unchanged to `gpio_write_data`, then calls
`gpio_stop`. There is no packed-duration translation or carrier-divider
calculation in that loop. The byte helper sends eight bits MSB-first,
then calls `gpio_check_ack`, which samples SDA and returns its raw level.
**The caller ignores that return value**, performs no ACK-based retry,
and returns the clamped byte count. A failed user copy returns `-EFAULT`.
GPIO-operation errors are likewise not checked by these paths.

Consequences for a HAL adapter:

- The existing 112-byte and 232-byte frames fit the syscall limit.
  A larger frame is truncated; do not use a generic write-all loop to
  split it, because each syscall starts a separate bus transaction.
- A positive write result proves neither controller acceptance nor optical
  transmission/completion. Do not equate it with an observed IR output.
- Serialize controller operations in one owning service: the private
  buffers and learning-mode state are shared, and the traced read/write
  paths do not acquire a transaction mutex.

### Read framing and returned bytes

For nonzero requests, `ctrl_read` clears its receive buffer, runs an
initial delay loop, clamps the length to 255, and samples `ir_state`.
If state is low it returns zero without starting a byte transaction.
Otherwise, after GPIO handshake/setup, it sends:

```text
START  30 52  REPEATED-START 31  ...read bytes... STOP  (isOne == 0)
START  30 62  REPEATED-START 31  ...read bytes... STOP  (isOne != 0)
```

`30`/`31` occupy the write/read address positions of this I2C-like bus,
consistent with a seven-bit address `0x18`. The APK's leading `30` byte
therefore also supplies the bus write-address byte. This does not justify
using an ordinary Linux I2C device or assuming that all electrical/ACK
details conform to standard I2C.

Let `N = min(requested_length, 255)` and call successive received bytes
`q0`, `q1`, etc. A nonzero `q0` stops the transaction and returns raw `-1`.
On success, `q0 == 0`; the returned buffer is `[0, q1, ..., q(N-1)]`.
The implementation actually clocks **N+1 bytes**: `qN` is read but
discarded. This includes the one-byte request case, which clocks two
bytes and returns `[0]`. It returns `N` after a successful user copy,
or `-EFAULT` if that copy fails. Zero-length reads return immediately.
There is no receive checksum or record-length validation in this path.
`gpio_read_data` samples eight bits MSB-first and calls `gpio_send_ack`;
that helper pulses SCL without explicitly driving SDA low.

This locates the APK's zero discriminator at the controller boundary:
the kernel checks a received zero and places zero in buffer offset zero.
It does not synthesize learned pulse durations. Neither the initial
delay loop nor the clocking delays calibrate the optical waveform units.

### Exact ioctl contract

The third ioctl argument is logged but not used to configure anything.
The jump table at `0xffffff8009b73410` has seven slots, including one
unsupported hole:

| Request | Action before restoring state pin to input |
| --- | --- |
| `0x8002` | Drive state high |
| `0x8003` | Drive state low |
| `0x8004` | Unsupported: `-ENOTTY` |
| `0x8005` | Drive SDA high |
| `0x8006` | Drive SDA low |
| `0x8007` | Drive SCL high |
| `0x8008` | Drive SCL low |

All six implemented commands return zero after the GPIO calls, without
propagating GPIO errors. Other request numbers return `-ENOTTY`.
There is no carrier, duty-cycle, pulse-array, or IR-enable ioctl here.
In particular, passing `38000` as the argument does not set a 38 kHz
carrier.

**Boundary established:** these kernel paths transport bytes and manipulate
bus/enable pins; they do not implement an Android waveform encoder.
No phone-side carrier/timer initialization was found in the traced driver
lifecycle. The remaining waveform interpretation appears to belong to
the HXD019 controller, but this is not proof that its firmware is absent
from every partition in the backup. The packet's carrier and duration
fields still require controller-format evidence; a 16 us unit is not
proven by this trace.

### Reproducibility and offline verification

Reproducible extraction, with outputs directed to a separate analysis
directory rather than the backup:

```sh
unpack_bootimg --boot_img /path/to/backup/boot_a.bin --out /path/to/analysis
gzip -dc /path/to/analysis/kernel > /path/to/analysis/Image
uv tool run --from vmlinux-to-elf vmlinux-to-elf \
  /path/to/analysis/Image /path/to/analysis/vmlinux.elf
```

Use the NDK's ARM64 `llvm-nm` and `llvm-objdump` on the reconstructed ELF.
Unlike the APK's ARM32 Thumb helpers, this kernel is AArch64.

The [stock-driver verification harness](../tools/verify-hxd-driver.py)
executes original instructions from the decompressed, hash-checked
`Image`; the reconstructed ELF is not required for those checks:

```sh
uv run --script tools/verify-hxd-driver.py /path/to/analysis/Image
```

It verifies unchanged writes and the 255-byte cap, both learning-mode
read commands and exact returned buffers (including the discarded byte),
not-ready/error paths, all ioctl slots and argument independence, all
256 byte values through the real bit-shifting helpers, GPIO idle setup,
and the standalone learning command. Kernel services, user copies, and
GPIO boundaries are mocked. High ACK results are deliberately supplied
to establish that writes ignore them. Execution is bounded to the driver
and fails on unexpected external calls. Kernel virtual addresses are
rebased to low addresses inside the emulator; this is not a kernel boot,
concurrency test, bus-timing test, or hardware simulation.
The later custom-mode check likewise verifies only that `30 30 60` is
forwarded and SDA/SCL ioctl requests reach the mocked pins.

```text
97ac7e4a9971b25654c63efb527d96b8b5a44c5a9fc39e86158637feb9d0d782  stock boot_a.bin
9e6d27d5ff9f7c091fdee9bcbc00211adc3d73a41c4ac5e64ce52ccb2fad652c  decompressed stock Image
```

The original images were not changed. No userdata, NVRAM, identity
partitions, or attached device were accessed, and extracted firmware is not
included in this repository.

## 6. Stock resources and public HXD019 comparison

### Bounded stock-resource search

Read-only `debugfs` traversal of the supplied extracted A-slot images
covered 7766 directory entries:

| Image | Entries inventoried | Files content-scanned |
| --- | --- | --- |
| `vendor_a.img` | 2710 | 1847 |
| `system_a.img` | 3573 | 155 |
| `system_ext_a.img` | 820 | 58 |
| `product_a.img` | 663 | 27 |

The content scan covered vendor regular files under `/bin`, `/lib`, and
`/lib64`, plus OS configuration files under `/etc` with `.rc`, `.conf`,
`.xml`, `.sh`, `.prop`, or `.txt` suffixes, and `build.prop` files.
Search terms included `hxd019`, `/dev/ctrl`, `et_jni`, `hxd_irda`,
`irremote`, and the textual custom-mode command. This is a targeted
resource search, not an exhaustive disassembly or scan of compressed
application contents.

Findings:

- No HXD firmware/update/configuration candidate was identified among
  the 77 vendor `/firmware` entries or other inventoried filenames.
  `/firmware/remoteproc_scp` is a 32-byte all-zero file, not an HXD image.
  Opaque, differently named data was not proven unrelated.
- The only content-scan hit was `/vendor/etc/init/hw/init.project.rc`:
  a comment names **IR_HXD019E**, followed by `chmod 0666 /dev/ctrl`.
  This supports an E-family integration label, not a verified silicon
  revision or proof of the D-family datasheet's optional features.
- Both `/vendor/lib/hw/consumerir.common.so` and its `lib64` counterpart
  exist. The previously analyzed arm64 implementation uses LIRC, not
  `/dev/ctrl`; the scan found no alternate HXD JNI library or service.
- The stock `FactoryMode.apk` was additionally checked as a plausible
  factory-test implementation. It contains no `lib/` native members;
  its DEX had no matches for HXD, infrared, `/dev/ctrl`, `et_jni`, or
  consumerir identifiers. This is not a full behavioral audit of that app.
- No partition was mounted or changed. Userdata, NVRAM, identity
  partitions, and application-private data were excluded.

The manufacturer's [current product page](https://www.hxdkj88.com/product/product_show/itemid/1.html)
describes the family as OTP-based and using I2C-like communication.
That makes a controller with internally programmed firmware plausible,
but does **not** prove the phone's part is identical or that no update
resource exists elsewhere. The bounded result is: **no relevant blob was
found in these inspected resources**, not "the backup cannot contain one."

### Public sources and agreement with the recovered implementation

The following sources were inspected directly; no third-party source or
remote-code database is incorporated into this repository.

| Source | Agreement / new evidence | Limits |
| --- | --- | --- |
| Manufacturer [HXD019D instructions, REV 1.3, page 1](https://www.hxdkj88.com/upload/file/1533202157.pdf) | Learning start `30 20 50`, read `30 62 31`, and 230-to-232-byte conversion agree with the extended route | Does not define individual timing/carrier fields |
| Manufacturer [driver overview](https://www.hxdkj88.com/news/news_show/itemid/1.html) | Describes dropping the initial zero and adding `30 03` plus the low-byte additive checksum | Framing agrees; it does not specify the APK's extra normalization |
| Manufacturer [STM32 porting notes](https://www.hxdkj88.com/news/news_show/itemid/5.html) | Separates communication clock delays from the roughly 20 ms transaction preamble | These bus timings do not establish optical pulse units |
| [IoTServ ESP8266 implementation](https://github.com/IoTServ/ESP8266_IRC/blob/0c27db989c17b9964c0669fb0037f834d3a33eaa/driver_lib/hxd019.c) | Both `30 52 31` and `30 62 31`; trailing received byte is treated as checksum; extended replay uses 232 bytes | Verifies checksum only for its short learning route; warns short replay did not work for its setup |
| [PQMarkinLi ESP32 short-route implementation](https://github.com/PQMarkinLi/IR_ESP32/blob/52d5e86bc1128c9127b58e35b48de25a9887d00c/hxd091d.c#L678) | Matching M708 packed decoding, `(x+2)/16`, parity adjustment, and 128-unit rejection boundary | Includes an ASCII `2048us` comment at that boundary, but is a different implementation/revision, not calibration of this phone |
| [PQMarkinLi ESP32 extended-route implementation](https://github.com/PQMarkinLi/IR_ESP32/blob/52d5e86bc1128c9127b58e35b48de25a9887d00c/hxd019_drv.c#L752) | Reads 229 bytes after the zero discriminator, then another byte described as checksum | Its checksum validation is disabled; it does not provide an arbitrary-frequency waveform encoder |

The public short-route `2048us` comment provides **additional documentary
support** for 16 us per normalized unit (`128 * 16 = 2048`) and raw M708
values approximately in microseconds. It is not a second independent
measurement, and shared code ancestry is likely. Retain the hypothesis
label: startup corrections, paired-value meaning, other record families,
and carrier encoding remain unresolved.

The trailing checksum interpretation explains the stock driver's
discarded `qN` byte for the expected 110/230-byte reads. It is consistent
with the public implementations, but the stock driver never verifies it
or exposes it to the caller. Arbitrary requested lengths do not establish
that a discarded byte is a valid checksum.

The manufacturer's download listings advertise Android source and
communications archives. The retrieved public archives
[`1484730519.rar`](https://www.hxdkj88.com/upload/file/1484730519.rar)
and [`1484730922.rar`](https://www.hxdkj88.com/upload/file/1484730922.rar)
contain a contact-the-manufacturer notice rather than the advertised
implementation. They did not supply a decoder, carrier table, or
controller firmware. No credentials, registration, or restricted resource
access was attempted.

Datasheet SHA-256:

```text
3dcbc8aab3a7b002339e620f6ab16ab152368b530dc7541d1ada562680104d06  1533202157.pdf
```

### Newly documented alternative: host-driven envelope mode

The manufacturer's REV 1.3 instructions describe an optional mode,
explicitly limited to **newer chip versions**:

1. Send `30 30 60` through the usual byte transport.
2. Keep SDA and BUSY high.
3. Use SCL as an envelope gate: low enables IR output, high disables it.

The page's waveform diagram distinguishes host SCL envelope transitions
from the modulated IR output. This could bypass learned-record packing
and its automatic protocol-toggle mutations. It is **not** documented as
host-generated carrier modulation, and the document does not specify a
carrier-setting command, carrier range, duty cycle, mode-exit sequence,
or how to detect support.

The existing stock write path forwards `30 30 60` unchanged, and
`0x8005`, `0x8007`, and `0x8008` can drive SDA high, SCL high, and SCL
low respectively. The offline driver harness now verifies those exact
software paths against mocked GPIOs. It does not emulate controller
recognition or optical output. Every ioctl restores BUSY/state to input,
so those commands alone do not guarantee the datasheet's held-high BUSY
condition.

This changes the implementation decision, but does not yet justify a HAL:

- **Packet route:** retain the existing kernel driver, but establish
  carrier/timing fields and representable-waveform limits first.
- **Envelope-gate route:** establish chip support, carrier behavior, exit
  behavior, and idle pin requirements. A robust version would need a
  bounded kernel-side timing operation, serialized ownership, and an
  error/cancellation cleanup path that restores IR-off. Repeated
  userspace sleeps and GPIO ioctls are not a reliable microsecond
  waveform scheduler, especially with per-call logging and GPIO
  direction changes.
- Do not advertise a 36/38/40-kHz range based on a gate-only interface.
  A fixed-carrier implementation would need an explicitly verified
  single-frequency contract, not silently ignore caller frequency.
- Do not send the optional command during offline investigation. The
  phone's E-family integration comment is not proof of support, and a
  write count cannot detect whether the controller entered the mode.

### E-variant follow-up: what can actually be established

Further primary-source inspection narrows the variant question:

- The manufacturer's [current family table](https://www.hxdkj88.com/file/storage/image/2026082711001744e195085.png)
  specifically lists **HXD019E** with I2C/GPIO communication and learning
  lengths `110/232Bytes`. HXD019EU(N) and HXD019EU(L) are listed as UART
  parts. Therefore an EU/EUN distributor entry is not sufficient evidence
  for the phone's GPIO-controlled part. The table's length labels are
  product descriptions, not replacements for the observed 110/230-byte
  input and 112/232-byte output contracts.
- The [HXD019E feature chart](https://www.hxdkj88.com/file/storage/image/202409181106004097b4384.png)
  explicitly advertises user-defined encoding. It also broadly claims
  learning/transmission of different frequency codes. These are family
  capability statements: the image gives no command bytes, frequency
  encoding, tolerances, mode-exit procedure, or identification register.
  Learning a carrier is not equivalent to accepting an arbitrary host
  frequency request.
- The manufacturer's [MTK integration notes](https://www.hxdkj88.com/news/news_show/itemid/9.html)
  say BUSY/CSN is a host input and that the HXD019 normally drives it high,
  while SDA/SCL are controller inputs. This explains why a host-input
  BUSY pin may be compatible with the custom-mode instruction to keep it
  high. It does not establish that BUSY remains high in optional mode.
  Do **not** solve that uncertainty by forcing a controller-driven line
  high from the host; output contention is possible.
- The manufacturer's [generic C transport notes](https://www.hxdkj88.com/news/news_show/itemid/3.html)
  document learning and transport, but add no carrier-setting or exit
  command. The public resources inspected still contain no E-specific
  programming specification resolving those operations.

The supplied APK was also checked for an alternate control surface:

- `ETIO.ioctl(int)` contains only `return-void`; it does not call the
  stock kernel's GPIO ioctls. The related ThreeMan ioctl wrapper is also
  a no-op. The Wi-Fi wrapper delegates to another no-op method, not the
  local controller.
- Targeted DEX method-name/string inspection and native export/string
  inspection found no named carrier/frequency setter for the HXD path
  and no literal `303060` / `30 30 60` string. This does **not** prove
  that an equivalent computed byte sequence cannot exist.
- The IO JNI exports are open, close, read, and write. The IR JNI exports
  cover initialization, learned/database conversion, database lookup,
  and `GetAirDelay`, not an exposed frequency setter.
- `GetAirDelay` at Thumb address `0x3208` is a table lookup: multiply the
  first Java integer argument by `0x1018`, add the second argument times
  four to a loaded table pointer, and return the word at offset four.
  There is no hardware call or mode-setting operation in that function.
  Its name is not evidence of a carrier-control interface.

Evidence checkpoint, after the E-specific follow-up:

| Required fact | Status | What is still missing |
| --- | --- | --- |
| Phone integration belongs to E-family | Stock comment and manufacturer interface table agree | Exact part/OTP revision or authoritative board specification |
| E-family offers custom encoding | Explicit manufacturer feature claim | Command/revision mapping for this phone |
| `30 30 60` gates SCL to modulated IR | Documented for newer D-family chips | Confirmation for the installed E variant |
| Arbitrary carrier selection | Not established | Packet/register layout, formula, supported range and duty cycle |
| Return to normal packet mode | Not established | Exit command or documented reset/power sequence and timing |
| Safe optional-mode feature probe | Not established | Read-only ID/capability query or documented response |

No positive E-specific command specification was obtained. Searching
secondary summaries or assuming that "newer" includes this phone would
not close these gaps. The optional-mode route remains a **conditional
design**, not an implementation ready to enable in the ROM.

The shortest useful manufacturer/board-vendor request is:

1. Identify the HXD019E part/OTP revision used by the HiBreak Pro 3.1.6
   integration, and whether it accepts `30 30 60`.
2. Provide the custom-mode carrier-setting command, units/formula,
   range, duty cycle, and whether it depends on an earlier learned packet.
3. Specify entry acknowledgment, support detection, mode exit, reset,
   power-on defaults, and required idle/turnaround delays.
4. Specify BUSY direction and behavior during gating; confirm SCL gate
   polarity, minimum pulse duration, maximum mark, and timeout behavior.
5. Alternatively, supply the `30 02` / `30 03` carrier and timing-field
   specification so arbitrary host waveforms can use packet mode.

Do not substitute a guessed `38 kHz` default or guessed power-cycle exit.
No vendor communication was sent and no controller command was executed.
If these specifications are unavailable, the next evidence must come
from a separately authorized controller test or a newly identified
encoder implementation; the existing static evidence cannot settle
exact silicon behavior.

SHA-256 of the inspected manufacturer charts:

```text
ab7195be741f32ae56e7d9f736218eb9c66a648067b36a71816d10321cb896c2  2026082711001744e195085.png
8af01027ce0774ebbf43bd2fe8e5216011e7f68561dac8b86d2434e35ab777dd  202409181106004097b4384.png
```

### Standalone learning/capture tool

The [capture CLI](../tools/hxd-learn.c) is a small, independent Android
arm64 executable. Its capture modes do not transmit IR. The updated tool
also has an explicitly selected fixed-packet transmit diagnostic described
below; it **does not implement learned-record replay or arbitrary-waveform
transmission**, use proprietary codec code, install a HAL, or change SELinux.
Building the tool does not authorize or start device testing.

Build on the host:

```sh
export ANDROID_NDK_HOME="$HOME/Android/Sdk/ndk/27.2.12479018"
tools/build-ir-tool.sh build/hxd-learn
```

The [build script](../tools/build-ir-tool.sh) uses the API-30 arm64 compiler,
treats warnings as errors, and refuses to overwrite an existing binary.
The executable is statically linked and has no APK/Unicorn or runtime-linker
dependency.

Only after explicit approval to deploy and enable learning, target the
intended device with `adb -s SERIAL`:

```sh
adb -s SERIAL push build/hxd-learn /data/local/tmp/hxd-learn
adb -s SERIAL shell chmod 0755 /data/local/tmp/hxd-learn
adb -s SERIAL shell /data/local/tmp/hxd-learn --help
# This command enables controller learning; it is NOT a read-only check.
adb -s SERIAL shell /data/local/tmp/hxd-learn capture \
  --timeout 25 /data/local/tmp/tv-power-extended.bin
adb -s SERIAL pull /data/local/tmp/tv-power-extended.bin local/tv-power-extended.bin
wc -c local/tv-power-extended.bin
sha256sum local/tv-power-extended.bin
```

Point the TV remote toward the phone's IR port and press one button after
the tool's prompt. Use a new filename for each capture; start with a
non-destructive TV function, such as volume, rather than a service-menu
or reset command. `--short` selects the alternative short learning method.
The saved record sizes are exactly **230 bytes** by default or **110
bytes** with `--short`. The tool neither converts nor truncates the record.
Local captures belong in ignored `local/`, not the source tree.

Behavior and limitations:

- The tool reserves a new mode-0600 output file before device access.
  Existing files and symlinks are refused. On failure it removes the
  incomplete file and reports an error, never a successful capture.
- It opens only `/dev/ctrl`, checks that it is a character device, and
  takes an advisory exclusive lock. This prevents concurrent instances
  of cooperating tools, **not** interference from HxdIR or another
  process ignoring the lock. Stop other IR software first.
- It sends exactly one `30 20 50` learning command, or `30 10 40` for
  short mode. It never writes the record back or sends `30 30 60`.
  Device writes are not retried or split into separate transactions.
- It waits at least 200 ms after the command when the deadline permits,
  then polls complete record reads, pausing up to 200 ms after a
  zero/not-ready result. Nonzero short reads are rejected, not padded
  or stitched together. A read error aborts rather than guessing whether
  it means SELinux denial or the driver's raw `-1` controller status.
- The monotonic deadline defaults to 25 seconds; `--timeout` accepts
  integers 1..60. It rejects a record returned after that deadline.
  It cannot enforce a hard deadline inside an uninterruptible kernel
  syscall. The controller's own learning timeout may be shorter.
- SIGINT/SIGTERM request cancellation; no undocumented cancel/reset
  command is sent. The chip may remain in learning mode until its own
  timeout (approximately 20 seconds). Wait for that timeout before
  trying again after an interrupted or failed session.
- A successful file has zero status and a nonzero payload, is saved
  byte-for-byte, and is flushed with `fsync`. These are basic capture
  checks, **not** proof of a replayable signal: the stock driver
  discards the receive checksum. Keep multiple captures of the same
  button for comparison. Records are controller data, not microsecond
  pulse arrays or ready-to-send packets.
- The updated tool rejects the exact 230-byte no-button control observed on
  stock 3.1.6, reports `No signal learned`, and removes the output. This is
  an exact-record exclusion, not a general decoder: it does not reject
  all records with `88 99 aa` or assert that every other record is valid.
  Complete reads also report elapsed time. The initially flashed tool
  predates this check and can still report success for the control record.
- An open/lock/access failure does not trigger root escalation,
  permission changes, or SELinux modifications. Mode `0666` does not
  guarantee access from ADB shell on an enforcing ROM.

Host-only tests, with no controller access:

```sh
python3 -m unittest discover -s tools/tests -p test_hxd_learn.py -v
```

The tests compile the real CLI against a
[mock syscall boundary](../tools/tests/native/hxd_learn_mock.c).
They check exact learning-command bytes, full output bytes and permissions,
both modes, delayed readiness, timeout, interruption, access/lock failures,
partial/error device writes, short/invalid/error reads, file-write and
flush failures, refusal to overwrite, and argument validation before
device access. They do not establish phone-side permissions or learning
success. Replay still requires a separate implementation and explicit
transmission approval; never `cat` the raw file to `/dev/ctrl`.

### Opt-in ROM capture service

On the tested custom ROM, ADB shell was denied `read write` access to
`ctrl_device` while SELinux was enforcing. Neither mode `0666` nor running
the image patcher with `--root` fixes that: `--root` only preserves an
already-existing `su` binary; it does not install root or enable `adb root`.

The separate [image overlay](../tools/add-ir-capture-to-gsi.py) installs the
static capture executable and a
[disabled, oneshot init service](../tools/ir/hibreak-ir-capture.rc).
It runs as **shell UID**, in a
[dedicated enforcing SELinux domain](../tools/ir/hibreak-ir-capture.cil),
not as root or `phhsu_daemon`. Only that new domain receives the added
`ctrl_device` permissions (`open read write getattr lock`); there is no
new shell-to-controller grant, ioctl access, or network grant.
The executable and capture destination are fixed. Its only mode parameter
is `debug.hibreak.ir_mode`, strictly validated as `extended`, `short`, or `tx-test`
before any file/controller access; unset defaults to `extended`. One init
service handles both modes, so mode selection does not introduce competing
capture services.

Prerequisites: the existing image tools, a host `secilc` compiler (Fedora/
Debian package `secilc`), and a **raw ext4 vendor image matching the phone**.
No compiler/dependency download occurs inside the overlay. It extracts
the GSI's platform/system_ext/product CIL and the matching vendor-version
mappings, plus the stock vendor CIL and versioned public policy. Compilation
targets SELinux policy version 30, supported by the stock kernel.
An independent ODM policy is not supported by this overlay.

```sh
# Choose fresh output filenames; builders refuse to overwrite.
tools/build-ir-tool.sh build/hxd-learn-service
# First apply the normal display/app patcher if those fixes are wanted.
tools/patch-gsi.sh /path/to/EvoX.img build/EvoX-display.img \
  build/HiBreakEink.apk build/a9_eink_server
python3 tools/add-ir-capture-to-gsi.py \
  build/EvoX-display.img build/EvoX-ir-capture.img build/hxd-learn-service \
  --vendor-image /path/to/extracted-vendor/vendor_a.img \
  --secilc /path/to/host/secilc
```

`--check-only` compiles the merged policy without copying/modifying an
image. Both inputs remain unchanged. The output's injected bytes, mode,
ownership and SELinux xattrs are checked, and its filesystem is checked
after shrinking. A changed platform policy-cache digest forces init to
recompile instead of accepting a vendor precompiled policy without the
new domain. That digest is an overlay cache-buster, not an AOSP build hash.
The compiler-produced binary is for host validation; boot init compiles
the installed CIL itself.

The selected EvoX 11.11 GSI plus stock 3.1.6 vendor already has **1,750
neverallow conflicts** in the unmodified host merge, including its broad
`phhsu_daemon` rules. The overlay compares baseline and modified compiler
diagnostics and **rejects any new conflict**, then compiles using the same
`-N` option Android init uses at runtime. This does not disable SELinux
enforcement or remove the baseline policy's restrictions. It also does
not fix EvoX's existing broad policy. The modified merge compiled with
zero additional conflicts. Boot and one explicit learning transaction were
subsequently tested with SELinux enforcing: the service ran, opened the
controller, saved 230 bytes, and exited with status zero. This proves
service/transport access, **not successful remote-signal learning**. The first
record arrived after about 22 seconds and contained `00 88 99 aa 00`,
32 bytes of `ff`, mostly zeros, and tail `f2 e1 51`; its meaning remains
unresolved and it must not be replayed as a confirmed TV command.
An immediate second Volume Up test and an explicitly authorized **no-button
control** both returned exactly the same 230 bytes (SHA-256
`1adcddd588b95e03b2f2200326c1e6f8ab97e7aeb4750628e8e793666d88b38c`).
Thus this observed record is not evidence of remote reception. The current
initial CLI's zero-status/nonzero-payload checks accept it: exit status zero means
the transport/save completed, not that learning succeeded. Further work
must distinguish this no-signal response and investigate receiver/learning
mode behavior before replay testing.

Offline follow-up confirmed:

- The APK's study task writes the same learning command, waits 200 ms, and
  reads the corresponding buffer size. No additional receive-enable
  command appears in that task. The driver open/release functions only
  set private data/return; they do not enable an optical receiver.
- Re-executing the stock driver verifies that mode `30 10 40` selects
  reads with `30 52 31`, while `30 20 50` selects `30 62 31`. There is no
  kernel-generated `88 99 aa` placeholder in the traced read path: returned
  payload bytes come from the controller bus (which does not prove optical
  reception or exclude bus errors).
- The native extended converter accepts the exact no-signal control and
  produces a checksummed 232-byte packet. It rewrites its first two header
  fields to `fe fe` and zero field 4 to `34`; these repairs do **not** make
  it a learned waveform. This is now an offline emulator regression case.

The next discriminating device test is short learning, preferably with a
no-button baseline and then the same button/position. These modes are
known learning commands, not invented configuration writes. A successful
short read alone would still require comparison against its own no-button
baseline. If neither mode responds to a remote, physical receive-path
availability, remote type/carrier, and placement remain unproven; software
analysis cannot establish that the board has a usable optical receiver.

The v2 image was subsequently flashed and short mode tested with explicit
approval. The no-button control returned 110 bytes after 21.771 seconds;
the Volume Up attempt returned identical bytes after 21.772 seconds:
`00 88 99 aa` followed by 106 zero bytes (SHA-256
`ae470e67b57d64608d8d4d5fa0ecbb2874f2fee56d067a361eee391f7b49e74e`).
Neither learning mode has demonstrated optical reception. V2 rejects only
the exact extended no-signal record; its short-mode candidate check still
accepts this newly observed short control, so status zero is not success
at learning. Preserve these baselines and do not replay them. Before more
image changes, establish that the remote actually uses IR for the tested
button and obtain evidence that this phone's board supports learning,
not merely transmission.

Building this image neither flashes it nor starts controller learning.
Back up first and use the repository's normal flashing procedure only
after separately deciding to install the test image. After boot, the
following checks are read-only:

```sh
adb -s SERIAL shell getenforce
adb -s SERIAL shell getprop init.svc.hibreak_ir_capture
adb -s SERIAL shell ls -ldZ /data/misc/hibreak-ir
adb -s SERIAL shell ls -lZ /dev/ctrl
```

Expect `Enforcing`, directory `hibreak_ir_capture_data_file` owned by shell
with mode `0700`, and controller `ctrl_device`. Before its first start, the
disabled service's state property can be empty; after a completed run it
is `stopped`. Shell cannot inspect or directly execute the dedicated
`hibreak_ir_capture_exec` binary under this policy; those denials are not
proof that init cannot start it. If data/controller labels differ, collect
init/SELinux logs rather than starting learning or disabling enforcement.

Only when ready to capture, stop other IR software, point the remote at
the phone's IR port, and explicitly trigger:

```sh
# Enables learning; not a read-only command.
# On the updated image, choose extended or short before triggering.
adb -s SERIAL shell setprop debug.hibreak.ir_mode extended
adb -s SERIAL shell setprop debug.hibreak.ir_capture 1
adb -s SERIAL shell getprop init.svc.hibreak_ir_capture
adb -s SERIAL shell cat /data/misc/hibreak-ir/result.txt
```

After the service reports `running` and its result file says
`Starting extended IR learning` (or `Starting short IR learning`), press
one remote button. The normal
deadline is 25 seconds; init also applies a 35-second service timeout.
Neither can instantly stop an uninterruptible kernel syscall.
Poll `init.svc.hibreak_ir_capture` until `stopped`, then read the result.
A candidate requires `Capture service exit status: 0` and a 230-byte
extended or 110-byte short record:

```sh
adb -s SERIAL shell cat /data/misc/hibreak-ir/result.txt
adb -s SERIAL shell wc -c /data/misc/hibreak-ir/record.bin
# Run in Bash; refuse to overwrite a previously saved host capture.
( set -o noclobber
  adb -s SERIAL exec-out cat /data/misc/hibreak-ir/record.bin > local/tv-volume-up-1.bin
)
wc -c local/tv-volume-up-1.bin
sha256sum local/tv-volume-up-1.bin
```

Each trigger **replaces the preceding service capture and result**, so
export a successful record before triggering again. Direct `adb pull`
runs in `adbd`, which has no access to this directory; `adb exec-out cat`
uses the permitted shell domain instead. Verify the exported file is
exactly 230 bytes (110 for short mode). The dedicated directory
is readable by ADB shell, but SELinux grants shell no write access there.
Files are mode `0600`. Once setup succeeds, failed captures remove the
record. A failure before log setup can leave an older result; if the
expected running/starting transition is not observed, inspect init/SELinux
logs instead of trusting an old file. Do not treat a successful `setprop`
as successful capture. Triggers during an already
running session do not queue another capture.

For cancellation, run `adb -s SERIAL shell setprop debug.hibreak.ir_cancel 1`.
Wait for the service to stop and for the controller's own learning timeout
before retrying. No undocumented controller reset/cancel is sent.
The original test image supports extended capture only. The updated image
adds short selection: set `debug.hibreak.ir_mode` to `short` before the
same capture trigger. Mode changes apply only to the next service start,
not an in-progress capture, and reset to the extended default after boot.
Use extended again by setting the property to `extended`. Both modes
replace the same result/record paths. Deploying a new standalone binary
to `/data/local/tmp` does not update the ROM service.
There is **still no learned-record replay, transmit HAL, or arbitrary-waveform
encoder**. The explicitly selected transmit diagnostics below are separate.

### Camera-only transmit diagnostic (v3 image)

The v3 tool adds the explicitly selected `tx-test` service mode. Normal
boot and the default capture mode do not transmit. This diagnostic sends
the manufacturer HXD019D instructions REV 1.3 section 1.1 sample:
`30 00 01 1c e3 00 ff 20 88 d7`. Its final byte matches the low-eight-bit
additive checksum. This is a documented compact database command, not
an invented encoding or replay of a no-signal record. Compatibility with
this phone's controller/code database is unverified.

It issues exactly five writes, waiting one second between completed writes,
then exits. Any failed/partial write aborts without retry. It uses the
same character-device check/advisory lock and supports signal cancellation.
It preserves the last capture record but replaces `result.txt`. There are
no GPIO ioctls, carrier guesses, or unrestricted user-supplied packets.
No additional SELinux permission is needed.

**The sample's appliance action is unknown. Aim away from appliances.**
First verify the observing camera can see the LED on a working IR remote
(the front camera may have less IR filtering). Record video of the phone's
IR window; this is more likely to catch brief pulses than a still photo.
After installing v3 and separately authorizing transmission:

```sh
adb -s SERIAL shell setprop debug.hibreak.ir_mode tx-test
adb -s SERIAL shell setprop debug.hibreak.ir_capture 1
# Wait for the service to stop, then inspect the result.
adb -s SERIAL shell cat /data/misc/hibreak-ir/result.txt
# Restore capture mode before any later trigger.
adb -s SERIAL shell setprop debug.hibreak.ir_mode extended
```

`Transmit test service exit status: 0` establishes only that five controller
writes completed. Visible flashing would establish optical output, not
correct carrier/timing or TV compatibility. No visible flash is inconclusive:
camera filtering/exposure, an unsupported sample database command, or
hardware/driver behavior can all prevent an observation.

On-device v3 test: with SELinux enforcing and explicit approval, all five
sample-packet writes completed and the service exited zero after 4.225
seconds. The user observed IR flashes through another phone's camera.
This confirms optical transmission for this sample on the custom ROM.
The service stopped and its mode was restored to extended capture.
It does not establish carrier/timing accuracy, appliance compatibility,
arbitrary-waveform support, or a functioning optical learning receiver.

### One-button TCL Volume Up test (v4 image)

The optional **HiBreak IR Test** launcher app provides one button, so a
computer is not needed next to the TV. It targets the user's TCL 43S525
Roku TV. The public
[TCL Roku TV IR reference](https://raw.githubusercontent.com/Lucaslhm/Flipper-IRDB/main/TVs/TCL/TCL_Roku_TV.ir)
lists NECext address bytes `EA C7` and Volume Up command bytes `0F F0`
for related TCL Roku models, including 65S525. This is a candidate for the
43S525, not a verified command for this particular TV.

The fixed experimental HXD packet is:

```text
30 00 01 0f f0 ea c7 00 00 e1
```

It uses the recovered compact layout `30 00 F KEY[2] COM[4] checksum`.
The sum of the first nine bytes modulo 256 is `E1`. **Choosing F=1 for
NECext, address byte order, and zero-filled remaining custom-code bytes
are hypotheses**, not results of the native codec verification. This
does not identify the carrier-frequency formula. It asks the controller
to use its compact protocol slot, which may have its own timing/repeat
behavior. One successful device write is not proof of correct optical
output or appliance response. No proprietary database/code is included.

Each explicit tap makes one property request, which starts a disabled,
oneshot, shell-UID init service and issues **one device write**. There is
no automatic emission at app launch/boot, long-press loop, host repeat,
learning, or retry. The button is disabled while awaiting a result.
Status is matched against a per-request token; stale results are ignored.
After ten seconds without a matching result, the UI explicitly reports
that transmission is unknown. That timeout does not cancel an in-flight
kernel write. The app does not report that the TV responded.

The APK has no Android permissions and cannot open `/dev/ctrl`. Only its
privileged-system installation with the exact package
`com.hibreak.irremote` receives the dedicated app SELinux domain. That
domain can set only the new request property; it receives no broad
`debug_prop` grant. The existing transport domain can publish only the
new result property. An ordinary sideloaded copy does not receive this
access. The test APK uses the signer's bundled **debug key**, not a
production signing identity; do not ship this diagnostic as a production
remote or treat its signing key as private.

Build with the same apktool, signer, and NDK prerequisites as the display
app (no Gradle, Android platform SDK, or vendor APK required):

```sh
export ANDROID_NDK_HOME=/path/to/android-ndk
bash tools/build-ir-remote.sh build/HiBreakIrRemote.apk
bash tools/build-ir-tool.sh build/hxd-learn-remote
python3 tools/add-ir-capture-to-gsi.py \
  /path/to/display-patched-without-ir.img build/HiBreakPro-ir-remote.img \
  build/hxd-learn-remote \
  --vendor-image /path/to/matching-stock-vendor.img \
  --secilc /path/to/secilc \
  --remote-apk build/HiBreakIrRemote.apk
```

Start from an image without an earlier IR overlay. The image includes
the APK, service, narrowly scoped policy, property contexts, and privileged
app mapping; installing the APK alone on the old image is insufficient.
Existing capture/camera diagnostics remain available, but are never
triggered by this app. TCL requests preserve both `record.bin` and the
capture `result.txt`; their separate log is
`/data/misc/hibreak-ir/tcl-result.txt`. For troubleshooting after an
explicit test:

```sh
adb -s SERIAL shell getprop init.svc.hibreak_ir_tcl
adb -s SERIAL shell getprop debug.hibreak.ir_tcl_result
adb -s SERIAL shell cat /data/misc/hibreak-ir/tcl-result.txt
```

The host build verifies APK signature/alignment, the full GSI/vendor policy
merge with no additional neverallow conflicts, and injected image contents
and filesystem integrity. Mock tests check exact packet/checksum, one
write, no retries, invalid tokens, failed/partial writes, busy device,
result publication failures, stale-result rejection, UI timeout, and both
overlay variants. **Boot-time app labeling/property access and the TV's
response still require testing after flashing v4.** After flashing,
unlock, open **HiBreak IR Test**, point the IR window at the TV, and tap
**Send Volume Up (experimental)** once. No computer is needed for that
button press. App installation, JNI library loading, and the actual
four-element launcher UI were checked on the existing ROM without
pressing Send or transmitting.

#### v4 boot regression and v5 correction

After flashing v4, the dedicated `hibreak_ir_remote` domain was selected
correctly, but ART aborted before app creation:
`Could not create private region after zygote fork: Failed to initialize
memory file: Permission denied`. The matching AVC denied writing
`memfd:jit-cache`, labeled `tmpfs`. Membership in `appdomain` alone does
not reproduce Android's per-domain `app_domain` macro expansion.
The earlier UI check used the old ROM's ordinary app domain, so it did
not exercise this policy.

The v5 overlay adds the same `tmpfs` to `appdomain_tmpfs` file transition
and scoped JIT-memory permissions used by the base ROM's `priv_app`,
plus its per-domain userfaultfd transition and permissions. It does not
grant writes to generic `tmpfs`, disable JIT, change the IR command, or
relax SELinux enforcement. A regression test requires these runtime
rules. The corrected image still needs a post-flash launch and
explicitly authorized transmission test; host policy compilation alone
cannot establish that the app runs in its new domain.

#### v5 startup regression and v6 correction

On the flashed v5 image, ART successfully initialized its JIT memory.
The next startup blocker was a service-manager denial for `activity`,
type `activity_service`, from `hibreak_ir_remote`. The standard
`priv_app` domain explicitly grants discovery of `app_api_service`;
`appdomain` membership does not include that grant.

The v6 policy grants the dedicated domain discovery of Android's public
app API services, rather than all service-manager types. Reviewing the
base ROM's explicit `priv_app` startup rules also identified its native
library execution, app-data symlink, and system-linker execution grants;
these are included for this JNI app and its installed updates. Existing
`appdomain` rules already supply Binder calls and app-data access through
attribute expressions, so those rules are not duplicated. IR/property
permissions are unchanged. Regression tests require both runtime memory
and service-discovery/native-loader rules. Actual launch still needs
validation under the corrected policy after flashing v6.

On the flashed v6 image, the user confirmed that the control works on
the TV. This establishes appliance response for the fixed
`30 00 01 0f f0 ea c7 00 00 e1` packet and the on-phone request path.
It supports the compact F=1, key/custom-byte mapping for this command,
not all NEC addresses/commands, an exact carrier frequency, or the
arbitrary-waveform codec.

### Experimental standard Android NEC adapter (v7)

This opt-in adapter connects **ordinary `ConsumerIrManager` clients**
to the existing controller. It recognizes a tightly bounded NEC envelope
and constructs the same compact F=1 packet layout as the working TCL
button. It does not use learning or proprietary native libraries/tables.

Supported input contract:

- Exactly **38000 Hz requested**. This is the nominal NEC protocol carrier,
  not a measurement of the HXD output; the compact protocol slot selects
  the controller's actual carrier. The HAL advertises only `[38000,38000]`,
  replacing the unrelated stock six-frequency table.
- One NEC/NECext frame: 9000/4500 us leader, 32 LSB-first bits using
  560 us marks and 560/1690 us spaces, and a final 560 us mark.
  Recognition allows +/-15% per interval and canonicalizes to the
  controller's built-in NEC protocol; it does not preserve exact timings.
- Exactly 67 durations, or 68 with a final idle gap of at least 10000 us.
  Every duration must be positive, and the complete request is limited
  to 2000000 us with overflow-safe checks.
- NEC's command complement must be valid; both ordinary complemented
  address bytes and NECext's independent address bytes are accepted.
  Command/address combinations other than the confirmed TCL Volume Up
  remain experimental.

Standalone NEC repeat frames, multiple frames in one array, NEC variants
with a 16-bit non-complemented command, RC5/RC6/Sony/AC and other raw
waveforms are rejected **before controller access** with a logged HAL
error. No frame is dropped/truncated to make an unsupported request fit.
Apps that send a single supported full frame per call can use this path;
an app that batches a press plus repeats in one pattern will not work
with this first implementation. No prior-command state is retained to
guess standalone repeat intent.

The adapter exposes the Android 12 legacy `consumerir` module ABI
(`HMI`), loaded by the already running vendor HIDL IR service. A
`post-fs` init action bind-mounts the system-supplied arm64 module over
`/vendor/lib64/hw/consumerir.common.so`, before `class hal` starts.
This changes the module visible at runtime, **not the vendor image on
disk**; only the new system image needs flashing. Its narrow SELinux
overlay permits init's file mount and permits `hal_ir_default` to
read/execute the module and read/write/lock `ctrl_device`. Ordinary
apps receive no device or private-property access. SELinux stays
enforcing. Reflashing the pre-HAL system image removes the bind action.
The separate v6 diagnostic button remains available.

Requests are serialized with a process mutex and the same advisory
controller lock as the diagnostic services. Each accepted frame uses
one ten-byte write. Failed/partial writes are logged, returned as errors
and never retried. After a successful write, ownership is held for the
requested envelope duration plus a conservative 120 ms guard. This
is **unmeasured experimental pacing**, not an ACK or optical-completion
guarantee; the kernel ignores controller ACKs and exposes no completion
notification. Controller-internal repeats are still unmeasured.
Consequently this is not yet a timing-faithful, fully conformant generic
Android IR HAL.

#### Build and validate

The NDK omits legacy `libhardware` headers. Supply public AOSP headers
from matching `android-12.0.0_r1` checkouts, preserving their include
directories. An `AOSP_HEADERS` directory can contain symlinks `hardware`
to `hardware/libhardware/include/hardware`, `cutils` to
`system/core/libcutils/include/cutils`, and `system` to
`system/core/libsystem/include/system`. The consumerir header includes
hardware/graphics headers transitively; do not replace these with
handwritten ABI stubs. Keep dependencies in ignored local storage.
Android 12 public headers and NDK 27.2.12479018 were used for this build.

```sh
export ANDROID_NDK_HOME=/path/to/android-ndk
export AOSP_HEADERS=/path/to/aosp-include
bash tools/build-ir-hal.sh build/consumerir.hxd.so
python3 -m unittest tools.tests.test_hxd_nec tools.tests.test_hxd_learn \
  tools.tests.test_ir_overlay tools.tests.test_ir_remote
python3 tools/add-ir-capture-to-gsi.py \
  /path/to/display-release-without-ir.img build/HiBreakPro-ir-nec-hal.img \
  --vendor-image /path/to/matching-stock-vendor.img \
  --secilc /path/to/secilc \
  --hal-module build/consumerir.hxd.so --check-only
```

This command preflights without creating an image. Remove `--check-only`
only when ready to package. For optional comparisons, build the private
app and tool and pass `--diagnostics-binary build/hxd-learn-remote
--remote-apk build/HiBreakIrRemote.apk`. Build the ordinary test app
with `bash tools/build-ir-api-test.sh build/AndroidIrApiTest.apk` and
either sideload it or opt in using `--api-test-apk`.
The HAL transport tests use official headers
from `AOSP_HEADERS` (default `local/ir-hal-headers`), skipping that ABI
test if headers are unavailable. Encoder tests need only a host C compiler.

The host tests cover exact TCL bytes/checksum, randomized NEC/NECext
addresses/commands, timing boundaries, atomic unsupported-input rejection,
duration overflow, ABI/callbacks, busy/non-character controllers,
partial/interrupted writes without retry, pacing interruptions, concurrent
requests, and image content/label roundtrips for all overlay variants.
An arm64 query-only probe successfully loaded the module on the phone,
opened its HAL device, queried the single 38000 Hz range, and closed it
**without transmitting**. That probe runs as shell; it does not verify
vendor linker namespaces or the post-boot HAL domain.

The separate **Android IR API Test** APK uses only the public API and
normal `TRANSMIT_IR` permission. It was installed and launched under
`untrusted_app` on v6; its send button correctly remained disabled
because the old HAL still advertises six ranges. No send was requested.
It enables sending only when one exact 38000 Hz range is reported.
The app's only send button constructs the known TCL NECext waveform,
not an HXD packet. It explicitly warns that Android's void `transmit`
return does not prove HAL success.

After flashing v7, first check (without sending):

```sh
adb -s SERIAL shell getenforce
adb -s SERIAL shell 'cat /proc/mounts | grep consumerir'
adb -s SERIAL logcat -d -s HibreakIR
adb -s SERIAL shell am start -n com.hibreak.irapitest/.MainActivity
```

Expect the adapter-loaded log and the API test app reporting a single
38000 Hz range. A bind-mount/module-load error must be fixed before
transmitting; do not mistake the original diagnostic app working for
standard-API success. Then, only when ready for a live test, aim at the
TV and tap **Send Volume Up via Android API** once. Confirm a matching
`HibreakIR` write log and actual TV response. Follow with an existing
ordinary IR app using one full NEC frame.

After the v7 flashing/test instructions, the user reported "it works".
This is user-reported end-to-end success for the standard Android API
TCL Volume Up test, following the earlier private-path success on v6.
No independent post-flash logs or optical measurements were collected
for this confirmation. Other ordinary IR apps, additional NEC commands,
controller-internal repeats, exact carrier/timing, and optical completion
remain unverified. This result does not establish arbitrary-waveform support.

#### IR Blaster carrier compatibility (v8)

The user's IR Blaster app reached the v7 HAL, but logged unsupported
waveforms. Its `NecProtocolEncoder` and `Nec2ProtocolEncoder` use **38222
Hz**, 562 us marks, 562/1687 us spaces and an optional final gap, whereas
v7 deliberately accepted only exactly 38000 Hz. The user identified the
failing button as NEC, 38.2 kHz, code `57E3E916`, 68 durations. That stored
MSB-first code decodes to NEC wire bytes `EA C7 97 68`, the candidate
TCL Power command, not Volume Up.

With explicit user approval, v8 accepts **38000 and 38222 Hz only**, and
advertises two singleton carrier ranges. Both select the identical built-in
NEC protocol slot; this is intentional nominal-carrier canonicalization,
not two measured or independently programmable output carriers. Nearby
values such as 38200 and 38400 remain rejected, rather than silently
clamping arbitrary inputs. No app-side protocol definitions are changed,
so USB and other phones keep their original carrier requests.

The encoder regression test reconstructs the app's MSB-first
`57E3E916` Power and `57E3F00F` Volume Up waveforms with 562/1687 us
timings and 108800 us final-gap padding. Both carrier aliases must
produce the exact expected HXD packet; unsupported nearby frequencies
must still fail. The updated diagnostic API client expects both singleton
ranges, and the query-only native probe checks the same advertised values.
HAL logs now include rejected request frequency/count and explicitly
describe accepted carrier canonicalization.

The user can keep the existing IR Blaster APK and button settings after
flashing v8. The old v7 API-test APK expects one carrier range and will
disable its button on v8; install the updated API-test APK if using that
diagnostic. Other protocol limits are unchanged: NECx1/NECx2's 4500 us
leader, non-NEC protocols, and bundled repeat sequences are not enabled
by this frequency-alias change. Post-flash testing from IR Blaster remains
necessary; this update does not establish that the user's full remote
database is compatible.

The user subsequently confirmed that IR Blaster works with v8. This
confirms the tested NEC command through that app; it does not broaden
the supported protocol contract.

#### Release preparation and review hardening

The current overlay's release command uses `--hal-module` with no
diagnostic binary or APK. It installs the standard adapter only.
Both test apps are explicit opt-ins: `--remote-apk` requires
`--diagnostics-binary`, while `--api-test-apk` independently adds the
ordinary API test app. Capture/camera services, their binary, private
request properties, and diagnostic-domain contexts/policy are absent
from the HAL-only configuration. The optional old positional binary
argument remains an explicit diagnostic opt-in for earlier commands.
See [the release build procedure](BUILDING.md#optional-ir-support-for-a-release-candidate)
for preflight and eventual packaging commands. No new release image
was packaged during this preparation.

Review hardening keeps a shared post-write ownership guard in both the
HAL and diagnostic transmitter, including the diagnostic's last packet.
Fixed sample/TCL commands use a conservative 108800 us envelope plus
120 ms; HAL requests use their validated envelope plus the same guard.
This remains unmeasured pacing, not a controller completion notification.
Signal-interrupted sleeps finish the guard before releasing the lock.
Regression coverage checks that a second lock owner is excluded during
the diagnostic guard and can acquire the lock after completion.

Before any output image is created, the overlay checks HAL ELF program
headers/segments, a terminated dynamic table, an exported arm64-sized
`HMI` object, a restricted set of Android runtime dependencies, and absence
of text relocations. Host `readelf` (`binutils`) is required for HAL builds.
Malformed/truncated and unrelated shared-library inputs are rejected;
these checks do not replace runtime linker/ABI testing.

The optional private test app now recovers its request token and start
time from existing properties when recreated, including after process
restart. It resumes status polling without sending and keeps sending
disabled while the init service is running, even if a result has already
been published or ten seconds have elapsed. Without a running service,
an unanswered request times out explicitly. Tests simulate erased
process-local state and verify no duplicate property request is made.

## 7. Recommended next investigation

1. Resolve the specific unanswered questions in the E-variant checklist
   above through manufacturer/board-vendor documentation or a newly
   identified implementation. The targeted public-source and supplied-APK
   follow-up did not expose a carrier setter or exit command; do not
   repeat broad web/firmware scans without a new lead. Continue offline
   record analysis where it can constrain timing/carrier fields.
   Approximately 16 us per normalized unit remains uncalibrated despite
   public-source corroboration. Do not enable either HAL route on that alone.
2. Extend complete short-record coverage to more segment classifications
   and protocol-specific waveform toggle changes. The harness now covers
   the original 45 isolated/packet vectors, complete short-record helpers
   and wrapper acceptance/rejection, and 22 protocol-scale hypotheses.
   JNI and hardware semantics remain unverified. Do not open the IR device
   or transmit during codec analysis.
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
