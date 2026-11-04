# Stock resources and HXD019 variants

## Bounded stock-resource search

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

## Public sources and agreement with the recovered implementation

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

## Newly documented alternative: host-driven envelope mode

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

This is a documented alternative, but the current HAL does not use it:

- **Packet route:** the existing adapter uses the bounded compact NEC packet
  route; generic timing/carrier fields remain unknown.
- **Envelope-gate route:** support for this phone's controller variant,
  carrier behavior, exit behavior and idle-pin requirements are unknown.
  A robust implementation would need a bounded kernel-side timing
  operation, serialized ownership and an error/cancellation path that
  reliably restores IR-off. Repeated userspace sleeps and GPIO ioctls are
  not a reliable microsecond waveform scheduler.
- Do not advertise a 36/38/40-kHz range based on a gate-only interface.
  A fixed-carrier implementation would need an explicitly verified
  single-frequency contract, not silently ignore caller frequency.
- The optional mode was not used for the implemented adapter. The phone's
  E-family integration comment is not proof of support, and a write count
  cannot detect whether the controller entered the mode.

## E-variant follow-up: what can actually be established

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
