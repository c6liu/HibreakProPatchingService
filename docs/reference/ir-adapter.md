# Android IR adapter

**Yes.** The implemented route replaces the legacy module visible to the
existing HIDL IR service; it is a bounded translation layer, not a new
appliance protocol. Android IR defines carrier frequency and pulse timing,
not NEC/RC5/etc. encoding. Only the NEC/NECext subset described below is
implemented.

The patching project's [build guide](../build/README.md)
preserves stock vendor and patches an ext4 system/GSI image. Its current
display patcher does not add an IR HAL or new SELinux policy; it relies on
the existing `phhsu_daemon` domain for its display daemon.
Adding a HAL is therefore additional ROM integration, not a switch in the
current display service.

The explored routes:

| Route | Benefit | Required integration |
| --- | --- | --- |
| Replace the legacy Consumer IR module with an HXD adapter | Reuses the running HIDL service and framework plumbing | Correct module selection/ABI, offline vendor change or verified library overlay, and HAL access to `ctrl_device` |
| Add an AIDL `android.hardware.ir.IConsumerIr/default` adapter | Modern interface; AOSP Android 16 prefers declared AIDL IR over HIDL | Native service, build/install rules, init lifecycle, correctly scoped VINTF declaration, service labeling and SELinux policy; verify discovery and startup on the actual GSI |

The legacy HIDL module replacement is the implemented route because the
target image already runs that service. The AIDL alternative was not
implemented; do not infer that copying a service or VINTF file into an
image would work.

The observed `hal_ir_default` vendor policy explicitly grants `irtx_device`
access but has no explicit grant to `ctrl_device`. Replacing only the
transmit function can therefore leave an access failure. Do not repurpose
the display daemon's domain as an IR HAL without checking all required
device, Binder, and service-registration permissions.

Current implementation properties and remaining qualifications:

- Input frequency, frame shape, duration positivity/total, NEC command
  complement and array length are checked before device access. Unsupported
  patterns are rejected rather than approximated. Total duration is capped
  at two seconds.
- Requests use a process mutex and nonblocking advisory controller lock,
  then one ten-byte write. Partial/error writes are not retried. The lock
  serializes cooperating clients only.
- After a complete write, the adapter waits for the requested envelope
  duration plus a 120 ms guard. This is conservative, unmeasured pacing,
  not hardware completion feedback.
- Device errors are logged and returned as HAL errors. Android framework
  callers may not receive every HAL error through the void API.
- It advertises only the two accepted **nominal request aliases**
  (38000/38222 Hz). They both select the controller's same built-in NEC
  carrier; the physical output frequency has not been measured.
- The kernel exposes no optical acknowledgment/completion notification.
  The HAL does not impose a cancellable deadline on a blocking kernel
  `write`, so a stuck driver operation is not covered by the pacing guard.

Do **not** symlink `/dev/lirc0` to `/dev/ctrl`. The ioctl contract and byte
payloads differ. A LIRC-compatible kernel frontend is an alternative, but
is more invasive and still needs the same HXD waveform translation.

IR learning is a separate optional feature. ConsumerIrManager exposes
transmission, not reception; adding a standard transmit HAL would not
automatically expose HxdIR's learning UI.

## Experimental standard Android NEC adapter

This opt-in adapter connects **ordinary `ConsumerIrManager` clients**
to the existing controller. It recognizes a tightly bounded NEC envelope
and constructs the same compact F=1 packet layout as the working TCL
button. It does not use learning or proprietary native libraries/tables.

Supported input contract:

- Exactly **38000 or 38222 Hz requested**. These are nominal request
  aliases, not measurements of the HXD output; both select the same
  controller-built NEC carrier. The HAL advertises these as two singleton
  ranges instead of the unrelated stock six-frequency table.
- One NEC/NECext frame: 9000/4500 us leader, 32 LSB-first bits using
  560 us marks and 560/1690 us spaces, and a final 560 us mark.
  Recognition allows +/-15% per interval and canonicalizes to the
  controller's built-in NEC protocol; it does not preserve exact timings.
- Exactly 67 durations, or 68 with a final idle gap of at least 10000 us.
  Every duration must be positive, and the complete request is limited
  to 2000000 us with overflow-safe checks.
- NEC's command complement must be valid; both ordinary complemented
  address bytes and NECext's independent address bytes are accepted.
  The user's tested TCL Volume Up command is confirmed; broader code
  database coverage has not been validated.

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

### Build and validation

Build and preflight the HAL using the current
[release procedure](../build/ir-overlay.md#overlay-details-and-development-options).
It requires the Android 12 public headers and a stock vendor image matching
the target phone's installed firmware. The ordinary API test APK is optional
and is not part of a HAL-only release. The host regression suite checks the
NEC encoder, HAL transport/error handling, locking and image overlay. These
tests are not physical waveform measurements or firmware-compatibility
certification.

The earlier API test was launched as an ordinary app under `untrusted_app`;
its send action used the public `ConsumerIrManager` API, not private HXD
access. The user reported the test command worked. A query-only native probe
also loaded the module and opened/queried it without transmitting; that probe
alone did not validate the HAL service's runtime domain. The later IR Blaster
compatibility update and user report are recorded below.

### IR Blaster carrier compatibility

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
disable its button on v8; use the updated API-test APK only if that optional
diagnostic is needed. The user's confirmation establishes that IR Blaster
works for the tested NEC command, not that every command in its remote
database is compatible. Non-NEC protocols and bundled repeat sequences
remain unsupported.

The user subsequently confirmed that IR Blaster works with v8. This
confirms the tested NEC command through that app; it does not broaden
the supported protocol contract.

### Validation safeguards

The current overlay's release command uses `--hal-module` with no
diagnostic binary or APK. It installs the standard adapter only.
Both test apps are explicit opt-ins: `--remote-apk` requires
`--diagnostics-binary`, while `--api-test-apk` independently adds the
ordinary API test app. Capture/camera services, their binary, private
request properties, and diagnostic-domain contexts/policy are absent
from the HAL-only configuration.
See [the release build procedure](../build/ir-overlay.md#overlay-details-and-development-options)
for preflight and packaging commands.

Review hardening keeps a shared post-write ownership guard in both the
HAL and diagnostic transmitter, including the diagnostic's last packet.
HAL requests hold the controller lock for their validated envelope plus
120 ms; this is unmeasured pacing, not a completion notification.

The overlay statically checks the arm64 HAL ELF, program segments,
terminated dynamic table, exported `HMI` object, runtime dependencies and
absence of text relocations before packaging. This does not replace runtime
linker/ABI validation.
