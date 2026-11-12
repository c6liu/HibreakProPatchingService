# 5. Stock firmware driver discovery

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

## Wiring and initialization

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

## Write contract and acknowledgments

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

## Read framing and returned bytes

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

## Exact ioctl contract

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

## Reproducibility and offline verification

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

The [stock-driver verification harness](../../../tools/diagnostics/verify-hxd-driver.py)
executes original instructions from the decompressed, hash-checked
`Image`; the reconstructed ELF is not required for those checks:

```sh
uv run --script tools/diagnostics/verify-hxd-driver.py /path/to/analysis/Image
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
