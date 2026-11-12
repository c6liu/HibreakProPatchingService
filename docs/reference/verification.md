# Post-install verification

## HiBreak action and overlay update

On 2026-11-11, the user reported that the updated overlay, screen-off actions,
and app/shortcut assignments work on the HiBreak. ADB subsequently confirmed
that the active system APK at
`/system/priv-app/HiBreakEink/HiBreakEink.apk` matches the supplied release APK
byte-for-byte. This is a successful user-reported device check, not an
independent exhaustive test of every gesture, shortcut provider, permission
state, or lock-screen condition; use the remaining checks below for broader
release validation.

Press Power right after the Bigme logo flashes, wait for boot, open E-Ink Settings and enable the accessibility service and
draw-over-other-apps permission. Top/bottom customization buttons have separate
single/double/long-press mappings, including screen-off mappings.
With the accessibility service enabled, fingerprint-sensor F9 events are consumed
without running a custom-button action. Verify that touching the power button
does not send F9 to the focused app, while pressing Power still locks/wakes the
phone and fingerprint unlocking still works. Other F9 input is also consumed.
Settings and the floating menu use standard Material 3 widgets and system
dynamic colors in light/dark mode. Check text contrast, selected refresh-mode
highlighting, all three switches, frontlight sliders, dialogs, and back
navigation on the physical e-ink panel after updating the source-built APK.
The Apps and Shortcuts picker supports search and preserves the current
assignment when cancelled. Modern launcher shortcuts require shortcut-host
access; app-provided shortcut configuration is available independently.
Screen-off app/shortcut launches wake the display without bypassing the
lock screen. Screen-off Clear Screen is removed, with existing assignments
migrated to Nothing. The overlay's top-right X closes it.
On Android 16, noninteractive keys may be dropped before reaching accessibility.
The root daemon therefore monitors the HiBreak's `mtk-kpd` side-key events without
grabbing the input device and forwards them to a receiver restricted to senders
with `INJECT_EVENTS`. The app accepts the bridge only for gestures starting with
the screen off; normal accessibility input continues to handle screen-on gestures.
Both the updated APK **and daemon** are required, so install this fix with an image
update, not just an APK update. Launching an app wakes the display but does not
bypass a secure lock screen.

```bash
adb devices
adb shell getprop sys.boot_completed
adb shell getprop debug.sf.enable_gl_backpressure
adb shell getprop debug.sf.enable_hwc_backpressure
adb shell dumpsys SurfaceFlinger | grep 'h/w composer disabled'
adb logcat -d -s hibreak-display a9EinkService
tools/device/collect-diagnostics.sh build/diagnostics-after-boot
```

Expect boot completion `1`, both backpressure properties `false`, and disabled
HWC. Init oneshot services normally show `stopped` **after successful completion**;
inspect logs, not that state alone. A running daemon also does not prove that
the app can send commands or that the panel responds.

The E-Ink app is a persistent system app: `adb install` fails with
"persistent app, not updateable". Update it by building and flashing a new image.

If the popup still shows the old order after flashing, check the active APK:

```bash
adb shell pm path com.lmqr.ha9_comp_service
```

A `/data/app/` path means an older installed update overrides the system copy.
After confirming the new image contains the corrected app, remove only that
package's update (this may reset app preferences):

```bash
adb shell cmd package uninstall-system-updates com.lmqr.ha9_comp_service
adb shell pm path com.lmqr.ha9_comp_service
```

The path should now be `/system/priv-app/HiBreakEink/HiBreakEink.apk`.
Check accessibility and overlay permissions again. The popup order is
**HD, Regal, Fast, Extreme, Hyper**.

Do not assume a successful package install proves mode speed or AOD appearance.
Test a selected mode, lock/unlock, and inspect the physical panel. See
[Findings](../research/README.md) for unsupported controls and the boot power-button issue.

## XRZ v2 overlay

If the image includes XRZ v2, follow its
[label and log checks](../build/xrz-overlay.md). Confirm SELinux remains
enforcing and check all four exact property labels. Do not interpret blank
shell `getprop` values as missing properties: the shell lacks read access on
the inspected build.

The [first v2 device snapshot](../research/display/xrz-graphics-policy.md#first-on-device-v2-check-2026-11-04)
confirmed the labels and loaded composer permissions, with no retained
composer crash or framework restart. It did not establish successful property
writes or stability across repeated sleep/wake and scrolling tests.

## Migration investigation history

The following sections preserve the chronological investigation, including
statements about what was not yet implemented or tested at each stage. They
are not current release instructions. The default release builder now installs
the working init bridge and the enforcing e-ink and display/AOD migrations;
the user reported that the separate migration test images worked. Upstream
PHH services remain outside those migrations. See the current
[build and device-verification guidance](../build/build-image.md#init-bridge-and-enforcing-migrations).

### Initial diagnostic gate

At this initial stage, migration was not enabled in release builds. The native daemon reports
its process context and the SELinux labels, owner/group and modes of its
hardware nodes, framework command executables and selected side-key input
device at startup. These probes only read metadata; failures are logged
explicitly. Build a new image with the updated daemon, retain your known-working
image, and after an authorized test boot collect:

```bash
adb shell getenforce
adb logcat -d -s a9EinkService:I A9SideKeys:I '*:S' | grep 'Policy probe:'
```

On the 2026-11-11 read-only inspection, the current daemon ran as root in
`phhsu_daemon`, while the accessibility app ran in `priv_app` with MLS
categories. The input devices were labelled `input_device`. Shell access
could not read the e-ink/frontlight node labels; generic `sysfs`/`debugfs`
genfs labels in the loaded policy do not establish each node's active label.
Do not replace this missing evidence with broad sysfs/debugfs permissions.

The next gate is a reviewed, host-compiled policy preserving every daemon
command, input ioctl, app socket connection and framework helper operation,
with no new ordinary or extended neverallow conflicts. Test that migration
in a separate image before migrating AOD/display helpers and upstream PHH
compatibility services. Those services still depend on `phhsu_daemon`; neither
its permissive declaration nor its grants can safely be retired yet.

### Host candidate progress

A host-only native-domain scaffold was compiled against the supplied EvoX
20260920/stock 3.1.6 pair. Adding direct writes to `system_prop` and
`vendor_default_prop` changed four existing neverallow diagnostic blocks even
though the total remained 1,774. Replacing those broad grants with a dedicated
system-internal control-property type introduced no new diagnostic blocks.
The compiled scaffold's native domain is enforcing.

This does not migrate a running service: executable/file/property contexts,
runtime node labels, framework-helper access, and MLS socket behavior still
need validation. In particular, `vendor.xrz.global_refresh_mode` currently
uses `vendor_default_prop`. Its migration requires scoped label/permission
preservation or a narrowly scoped property bridge, not a default-property
write grant. Keep the scaffold out of release images until all existing
commands and hardware paths have been wired and verified.

### Scoped controls and socket scaffold

The next host-only step uses five typed, exact `sys.hibreak.request.*`
properties. An init bridge writes the original refresh/AOD/vibrator/wake
properties without relabelling them or changing existing domains' effective
permissions. The new native core domain inherits read-only `system_prop`
access, but receives no `system_prop` or `vendor_default_prop` set grant.
Refresh and AOD bridge actions enumerate the supported values; the other
requests are typed integers and retain the daemon's existing numeric checks.
Bridge completion is asynchronous and is not an acknowledgement that the
property or hardware operation succeeded.

The socket scaffold allows the existing `priv_app` client to connect and
marks the daemon `mlstrustedsubject`: the loaded policy's socket `connectto`
constraint otherwise prevents the categorized app connecting to an s0 daemon.
This scaffold alone is not package-specific authentication; the separate
experimental migration build adds the peer check described below.

Validate only, without image creation or device changes:

```bash
/usr/bin/python3 tools/diagnostics/check-eink-migration.py "$BASE" \
  --vendor-image "$VENDOR" --secilc "$SECILC"
```

`tools/build/build-daemon.sh OUTPUT --enforcing-candidate` compiles the request
property route for host/development testing. **Do not substitute this binary
into a normal release image:** the bridge, domain transitions, executable
labels, hardware labels/permissions and framework execution path are not
fully wired in that early standalone candidate. At the time, normal builds
kept the direct-property behavior and did not install the candidate files.

The separate `--enforcing-migration-candidate` daemon build combines those
request properties with the user-tested property-only refresh and init e-ink
debugfs bridge routes. The separate host-only
`tools/display/hibreak-eink-bridge-client.cil` grants the new domain permission
to send the two bridge requests. Validate this against the tested bridge
image using `--with-init-bridge`; the full test-image/vendor pair retained
386 existing diagnostic blocks with no added blocks or changed existing
bridge-property permissions. The separate migration-image builder adds
frontlight access, socket authorization and service labelling. At that stage
those changes were not in normal release builds or device-validated.

The migration daemon obtains `SO_PEERCRED` for each connection and compares the
peer's Android app ID against `/data/system/packages.list`, rejecting malformed
registry input, missing packages and shared app IDs. This supports variable
UIDs and Android users without hard-coding the observed UID. It relies on
Android protecting that package-manager registry and the installed package's
identity; registry access fails closed and is logged. SELinux still permits
other `priv_app` clients to attempt a connection, but their UID must pass this
check before commands are read. Runtime DAC, app reconnection and peer
authorization remain to be tested.

The separate candidate labels exactly the two frontlight files and generates
rules to preserve their baseline effective `sysfs` file permissions before
adding daemon `open` and `write`. It uses the original synchronous hardware
writes. The matching vendor, node paths, runtime labels and DAC are still
device-validation gates; no frontlight or framework behavior is established
by the host policy checks.

On the full tested bridge image and matching vendor, the combined candidate
retained all 386 existing diagnostic blocks without additions. The two
frontlight labels preserved both baseline effective file permissions and
existing extended file permissions. An opt-in image was built separately and
its embedded daemon, service, contexts, init bridge and manifest checksum
were checked.

On 2026-11-11, the user tested that image and reported that both frontlight
and refresh controls failed. The daemon ran in enforcing `hibreak_eink`;
its main thread had a long-running `settings put secure
theme_customization_overlay_packages` child, and a side-key `am broadcast`
child was also still running. Device audit logs showed `system_server` denied
Binder `call` to `hibreak_eink`. Since the daemon waits synchronously for its
theme helper, a stuck helper can prevent subsequent socket commands from
being processed. The candidate now grants that exact Binder callback; a new
test image is required to determine whether it resolves the stalls and
restores the controls. Startup `getattr` denials for hardware probes are
separate diagnostic reads, not evidence that frontlight writes were denied.
The user subsequently reported that the Binder-callback test image works.
No logs or detailed regression matrix accompanied that report, so it does not
establish that every daemon feature or remaining PHH service was tested.

### Display and AOD helper migration candidate

The separate display overlay moves the five HiBreak helper services from
`phhsu_daemon` to an enforcing `hibreak_display` domain. Its policy includes
the SurfaceFlinger and framework service accesses needed by the scripts,
including Binder callbacks. Host policy checks against the user-tested daemon
image and matching vendor retained the same 386 diagnostic blocks, without
claiming the existing policy is neverallow-clean.

The old AOD marker and setup properties resolve to `system_prop`. A direct
replacement label that preserved all their existing effective permissions
changed neverallow diagnostics, so it was not used. Instead, the experimental
overlay keeps those labels intact, reads their legacy values on first use, and
stores migrated markers in two new exact, enum-typed persistent properties.
This keeps the existing AOD inversion behavior rather than removing it; the
normal release scripts remained unchanged at that stage. The new image and its embedded
scripts, policy, property contexts, unchanged daemon, and checksum have been
verified on the host. Boot, SurfaceFlinger, framework callbacks, AOD
transitions, and DAC still require device testing.

On 2026-11-11, the user reported that the display and AOD helper migration
test image works. No logs or detailed regression matrix accompanied the
report, so it does not independently confirm each individual feature or
the migration of upstream PHH services.

### Hardware and framework host investigation

On the inspected GSI, `/system/bin/am`, `input`, and `settings` are shell
scripts invoking `/system/bin/cmd`; `setprop` resolves to `toolbox`. The
host-only policy scaffold now includes executable, Binder and named-service
grants for these helpers. The GSI/vendor merge still has 1,774 parsed
diagnostic blocks and the scaffold adds none. This confirms policy rules
exist, **not** that Android framework authorization, side-key broadcasts,
input injection or theme changes work at runtime.

A separate host experiment labelled only the two expected frontlight nodes
with a new `sysfs_type` and the three e-ink nodes with a new `debugfs_type`.
Giving the core daemon access to the debugfs type changed an existing
`system/sepolicy/private/domain.te:2273` neverallow diagnostic. Compiling
with `-N` would hide that assertion failure; the experiment is not included
in the scaffold or an image.

Comparing a proposed frontlight label against the loaded policy's generic
`sysfs` type found **117 lost effective file-permission tuples** for other
domains, including some permissions for `init`. These counts are conditional
on the nodes actually using the generic label, which shell could not verify;
they are not evidence of which permissions are exercised on the phone.
Label changes must preserve reviewed existing behavior and use confirmed
resolved device paths before they can be packaged. Debugfs access may require
a different architecture or an upstream policy/device change rather than
weakening assertions.

On the full init-bridge test image, a subsequent host-only experiment assigned
the two frontlight paths a dedicated `sysfs_type`, preserved all 248 effective
generic `sysfs` file-permission tuples (including the 116 otherwise lost), and
added only init's file `write` permission. All 386 baseline diagnostic blocks
were unchanged. Device AVCs identified both nodes as generic `sysfs`, but
shell lacked permission to stat them, so DAC and the runtime behavior of the
proposed init bridge remain unverified. This policy experiment is not included
in an image; a property interface and client authorization are still needed.

### Debugfs alternative investigation (2026-11-11)

The stock 3.1.6 vendor backup's `hwcomposer.mt6877.so` (SHA-256
`7e2c21f74fdc7d0bdfca45614d0ff25b559717cc007eb7a5cd4b8c6a0a9c4c4e`)
was examined offline; the connected phone reported the corresponding stock
vendor build fingerprint. Shell could not read the installed composer binary,
so byte-for-byte identity with the backup was not established.

- In `CommitPolicy::checkLayersAndSetCommitInfo`, the composer reads
  `vendor.xrz.global_refresh_mode` at `0xef724` and, on a nonzero branch,
  uses its low bits in refresh-mode selection. This is a plausible way to
  influence future composer commits without the daemon's `global_mode`
  write. It does **not** prove equivalent global driver state or immediate
  behavior; the daemon currently writes both interfaces. In particular,
  the flagged HD value `2147483825` needs particular scrutiny because the
  composer's property helper calls `atoi` and returns a signed integer.
- The composer reads `vendor.xrz.auto_clean_enabled` at `0xef8fc` in a
  conditional refresh-mode/commit path, and `vendor.xrz.clean_frequency` at
  `0xee878` in `needCleanScreen`. These are potential composer-side controls,
  but no evidence establishes either as equivalent to the daemon's direct
  `clean_a2` toggle.
- `vendor.xrz.anti_flicker_enabled` is read at `0xf0180` and influences
  commit information. However, `DrmDevice::triggerEinkCommit` calls
  `mtk_set_anti_flicker` at `0xf5c28`; that function writes `0` or `1` to
  the same `/sys/kernel/debug/eink_debug/anti_flicker` node. Retained
  on-device logs showed those composer writes failing on this GSI. Thus
  setting this property alone is **not** a demonstrated debugfs-free
  replacement for Anti-Shake.
- The backed-up kernel contains `DRM_IOCTL_EINK_UPDATE` and
  `drm_eink_update_ioctl`, as well as `global_mode`, `clean_a2`, and
  `anti_flicker` debugfs names. The composer uses the DRM update ioctl for
  commits; string/symbol presence does not establish a safe independent
  interface for setting the three global controls.

The connected device's loaded policy permits the composer to read
`vendor_default_prop`, and init can set it; ordinary shell property reads
were denied. No properties, display modes or device files were changed during
the initial investigation.

On 2026-11-11, the user tested a separate property-only refresh image that
omits only the daemon's `global_mode` write while retaining `clean_a2` and
`anti_flicker`. The user reported that it works, and supplied daemon logs
showing successful property requests for all five mode values, including
`2147483825`. The user subsequently confirmed that all modes work and that
app switches and sleep/wake also work. This is encouraging device evidence,
but the logs establish property sets only; exact equivalence to the driver
write and composer receipt were not independently measured. Keep a working
image for recovery. Auto Refresh and Anti-Shake still use debugfs, and the
enforcing-domain migration remains incomplete.

### HiBreak Pro Color comparison (2026-11-11)

The public [HiBreak Pro Color project](https://github.com/dianqk/LineageOS_gsi_HBPC/tree/c1b0751b438a26498473f331b8d2f18b3603f17b)
uses a different device and vendor build. Its
[E-Ink daemon patch](https://github.com/dianqk/LineageOS_gsi_HBPC/blob/c1b0751b438a26498473f331b8d2f18b3603f17b/hbpc/patches/hibreak/vendor_a9_services/0001-HiBreak-Pro-Color.patch)
maps `au_br0/1` to `vendor.xrz.auto_clean_enabled` and `an_fl0/1` to
`vendor.xrz.anti_flicker_enabled`, without daemon debugfs writes. Its
[cleaning documentation](https://github.com/dianqk/LineageOS_gsi_HBPC/blob/c1b0751b438a26498473f331b8d2f18b3603f17b/hbpc/EINK-CLEAN.md)
describes `clean_frequency` as a separate full-screen ghost-clean interval,
not the `clean_a2` switch.

The monochrome device's composer reads the same properties, but its
anti-flicker property path still ends in a debugfs write, which its composer
has been observed to fail. A matching AVC or the precise failure cause has
not been established. The Color implementation therefore does not demonstrate
that property-only Anti-Shake works on this device.

On 2026-11-11, the user tested a separate image that replaced the daemon's
`clean_a2` write with `vendor.xrz.auto_clean_enabled`. Daemon logs showed
successful requests for both `0` and `1`, but the user reported that Auto
Refresh did not seem to work. A later kernel log contained
`auto_clean(0, 1, 0)` during updates; its field meanings and relationship
to the reported behavior were not established. Treat the property-only
approach as unsuccessful for this device test, not as a verified replacement.
The preceding property-only refresh image retains the original Auto Refresh
and Anti-Shake debugfs paths.

On the preceding test image, retained audit logs identified the active `clean_a2`
node as `u:object_r:debugfs:s0` and recorded denied daemon `open` and `write`
checks with `permissive=1` for `phhsu_daemon`; those particular denials were
not enforced. This confirms that an enforcing daemon cannot simply retain the
same access without further policy changes. The host policy experiment above
shows that adding its debugfs grant introduces a neverallow conflict.

### Stock 3.1.6 display-control implementation (2026-11-11)

The backed-up monochrome stock system and vendor images were inspected
offline. The stock `DisplayPolicyController.applyDisplayPolicy` obtains
per-app auto-clean and anti-flicker values and calls the corresponding
`XrzEinkManagerInternal` setters:

- `setAutoCleanEnable` sets `vendor.xrz.auto_clean_enabled` and then calls
  `nativeSetAutoCleanEnable`. The JNI registration in
  `libXrzFramework_runtime.so` maps that method to code which opens
  `/sys/kernel/debug/eink_debug/clean_a2` and writes `1` or `0`. Thus stock
  uses **both** the property and a direct driver write; setting only the
  property does not reproduce this implementation.
- `setAntiFlickerEnable` sets `vendor.xrz.anti_flicker_enabled`. The stock
  vendor composer subsequently calls its own anti-flicker debugfs writer,
  as described above. The JNI library also registers a native method that
  writes the node, but the inspected stock framework DEX calls the property
  setter rather than that native method in the per-app policy path.
- Stock `init.eink.rc` mounts debugfs at early init and requests mode `0666`
  on `clean_a2`, `anti_flicker`, and `anti_alias` during the `fs` trigger.
  File modes alone do not bypass SELinux, and the init commands' success on
  a running stock phone was not observed.

The backed-up vendor precompiled policy grants `system_server` and
`hal_graphics_composer_default` file access to `xrz_debugfs`; neither domain
is marked permissive in that policy. The stock platform CIL excludes
`xrz_debugfs` from certain debugfs neverallows. The stock platform digest in
the system image matches the vendor's precompiled-policy platform digest,
but this does not prove which policy or labels a running stock phone used.
The inspected compiled policy has no debugfs genfs entry for the e-ink
path or `xrz_debugfs`, and the label assignment mechanism was not established.
These stock-specific exceptions cannot simply be assumed to work under the
GSI's different policy and assertions.

The extracted stock `framework.jar`, `services.jar`, and
`libXrzFramework_runtime.so` SHA-256 values were respectively
`e7da2aa27e2161021dc5703afbd7304f8983973c99eca8322b766b49501b457a`,
`4d15e89e4682444ed01246099eab43a3897783be038285844fa74a42af52155d`,
and `9c82f344e4db0fc994e7b5ae3db8c70c57cdde0626d036a68b5d828730c83fd3`.
These findings are static evidence, not a stock-device runtime test.

### Init-only debugfs bridge investigation (2026-11-11)

The GSI platform policy's `domain.te:2273` debugfs neverallow excludes `init`,
but the inspected loaded policy has no `init` file allow for generic `debugfs`.
Retained audit logs show both `clean_a2` and `anti_flicker` labelled
`u:object_r:debugfs:s0`; access by the current `phhsu_daemon` was logged
with `permissive=1`, so those checks were not enforced.

A host-only CIL experiment introduced a `debugfs_type` for exactly the
`/eink_debug/clean_a2` and `/eink_debug/anti_flicker` genfs paths, with
`init` file `open` and `write` permissions. The parent directories were not
relabelled. It was compiled alongside the existing enforcing daemon scaffold,
using the extracted EvoX/stock-vendor baseline policies, without IR or XRZ
overlay policy changes:

| Policy input | Baseline diagnostic blocks | Candidate blocks | Newly changed blocks |
|---|---:|---:|---:|
| Original PHH policy | 1,774 | 1,774 | 0 |
| Exact 70-grant PHH reduction | 386 | 386 | 0 |

With assertion checks skipped for binary generation, the new daemon domain
remained enforcing. For the two nodes, comparing effective SELinux *file*
allow tuples for generic `debugfs` against the proposed type found no lost
tuples: the original policy had 19 existing tuples, and the reduced policy
had none. In each case the only additional file tuples were `init` `open` and
`write`. This comparison is conditional on the observed labels and does not
prove DAC permissions, genfs runtime labeling, ioctl behavior, all conditional
or MLS constraints, or actual hardware writes. The count of diagnostic blocks
is not proof that every violating rule was exhaustively reported.

This makes an init bridge a **candidate**, not a completed migration. An init
action could use exact typed `0/1` request properties and fixed-path `write`
commands; no daemon debugfs grant would be necessary. Before deployment,
verify the full post-IR/XRZ/reduction policy, property writers, node
ownership/modes, boot timing and relabeling, and restrict socket clients.
Property-triggered writes are asynchronous: setting a request is not an
acknowledgement of a successful hardware write. Test rapid toggles, repeated
values, app switching, sleep/wake, and failure reporting; Android init queues
actions and evaluates property triggers during boot as documented in its
[init language reference](https://android.googlesource.com/platform/system/core/+/refs/heads/android16-release/init/README.md).
The existing daemon's success/error semantics must not be assumed to carry
over. Nothing from this probe is installed into a normal release image.

An opt-in test image was subsequently built from the full IR/XRZ/PHH-reduced
property-only-refresh image. Its complete merged policy retained 386 baseline
neverallow diagnostic blocks with no changed blocks, and the two exact node
labels preserve the baseline file allow tuples while adding only init `open`
and `write`. The bridge request properties have exactly two effective
property-service writers: init and the existing `phhsu_daemon`. Focused host
tests cover the four fixed-value init actions and daemon request/error paths;
the built image's embedded daemon and init script were verified. This is not
an enforcing daemon migration. Device validation must include actual panel
behavior, init write errors, repeated/rapid changes, per-app changes, and
sleep/wake checked against the prior working image.

On 2026-11-11, the user reported that the init bridge test image works.
The user subsequently reported that all features work. No init logs or
detailed test matrix were supplied, so this is user-reported device evidence,
not independent confirmation of every hardware write or completion of the
enforcing-domain migration.
