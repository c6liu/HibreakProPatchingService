# Extended-record and database packet construction

The 230-byte branch in `StudyKeyCode` is separate from `compdata`. An
isolated run from `0x2a24` to `0x2b70` reproduces its normalization and complete
232-byte packet, stopping before JNI allocation/copy callbacks. All 22
synthetic extended vectors match the independent model in
[`tools/diagnostics/verify-hxd-codec.py`](../../../tools/diagnostics/verify-hxd-codec.py) **byte-for-byte**,
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

## Variable-length `30 01` branch

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
[correlation](protocol-correlation.md) narrows their timing interpretation.

**ROM-layer consequence:** choose a validated representation first, then
construct its fields explicitly. Reusing `StudyKeyCode` as a carrier-plus-
duration encoder would mix format-specific rewrites, sentinel handling,
and database replay without a proven mapping. The full hardware translation
is still unimplemented.

## Learned-data ingestion: where the numbers originate

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

## Complete short-record emulation

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
