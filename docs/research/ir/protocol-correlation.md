# Known-protocol correlation: useful evidence, not a clock calibration

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

## Reproducible binary landmarks

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
