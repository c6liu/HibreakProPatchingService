# Recovered normalization rules and offline verification

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

## M708 route

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

## `Modifywave` and `delfeng` route

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

## Segment metadata and status handling

`getfigure` first finds the maximum normalized stream value, then selects
up to three candidates at least `maximum - floor(maximum / 8)`. It compares
sequence regions and writes entry 1 as `(old_flags & 0x88) | classification`,
with classification values 0 through 3 on the examined branches. Entries 2
and 3 are selected segment counts rounded upward to even values. This is
much stronger evidence for segment/repeat classification than the function
name alone, but it still does not define the controller's repeat contract.

## Repeat investigation: host resends versus encoded segments

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

## Carrier investigation across three codec versions

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

**Current implementation consequence:** the adapter intentionally supports
only the validated NEC/NECext packet mapping described in the [adapter reference](../../reference/ir-adapter.md). The codec
analysis does not provide a generic mapping from Android frequency/timings
to HXD carrier and repeat controls. Appliance response to a known command
does not determine the exact optical waveform; a camera cannot measure its
carrier or precise timing.

`compdata` decrements its length argument before dispatch. It calls
`delfeng` even if `Modifywave` returned failure, and only invokes `getfigure`
when the selected normalizer returned zero. It does not propagate
`getfigure`'s return value. `learn_data_in_out` likewise does not check the
return from `get_remote_study_data` before continuing. A new translation
layer must therefore implement its own explicit validation rather than
treating the APK's returned array length as proof of successful conversion.

## Reproducible software checks

[`tools/diagnostics/verify-hxd-codec.py`](../../../tools/diagnostics/verify-hxd-codec.py) runs the original
Thumb instructions in Unicorn using synthetic records. It verifies the
library hash listed in [binary landmarks](protocol-correlation.md#reproducible-binary-landmarks). Isolated tests map selected helper code; complete
short-record tests additionally map the local ELF load segments and resolve
its internal references. Database/descriptor bytes stay in emulator memory,
not in the repository. No JNI callbacks, transport routines, Android
services, or device access execute. The APK and its proprietary code tables
are not included.

```sh
uv run --script tools/diagnostics/verify-hxd-codec.py /path/to/HxdIR.apk
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
checks in [Extended records](extended-records.md#complete-short-record-emulation) extend coverage beyond the isolated normalizers.
