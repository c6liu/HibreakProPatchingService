# Boot, sleep and the power-button report

**User-reported boot behavior:** after every restart or power-up, press the
Power button once right after the Bigme logo flashes. Otherwise, it may return to a
powered-off state. Treat this as a manual post-reboot step; this project does
not fix it.

A diagnostic reboot on 2026-10-26 without a physical Power press did not
reproduce that exact behavior: the device entered Android doze and remained
reachable over ADB. This observation does not invalidate the reported
power-button requirement.

Diagnostic details from that run:

- ADB returned about 12 seconds into boot.
- `sys.boot_completed=1` by about 33 seconds.
- Old boot helper sent `KEYCODE_SLEEP` at 05:56:31, then `KEYCODE_WAKEUP`
  two seconds later; the log records a successful wake.
- At 05:56:43 Android entered doze due to **timeout**, not a shutdown request.
- At 127 seconds uptime, ADB was still connected, boot complete was still 1,
  display state was 4 (`DOZE_SUSPEND`), and PowerManager reported `Dozing`.
- An ADB `KEYCODE_WAKEUP` later changed the state to `Awake`/display state 2
  and removed the AOD inversion marker. No physical button was needed.

Thus this observed instance was Android sleep/AOD, not a power-off. That does
not rule out a different intermittent PMIC, bootloader or kernel failure.
Retained boot reasons were `reboot` / `reboot,fastboot`; no Android shutdown
sequence was found for the observed interval.

The old helper forced a sleep cycle on **every** boot, based on a first-boot
workaround. The subsequent consolidated helper only woke by default. Its optional
legacy sleep/wake cycle is gated by root-set
`persist.sys.hibreak.boot_sleep_cycle=true`. This removes unnecessary boot-time
sleep, but **is not a verified fix for a genuine hardware power-off**. Normal
screen timeout and AOD remain enabled; this does not keep the screen awake
forever or change battery behavior.

On 2026-10-27, a comparison image removed only the automatic wake helper,
retaining the other display fixes and the same APK and daemon. The user
reported repeated crashes afterwards. Read-only collection confirmed composer
crashes at 13:20:34, 13:22:04, 13:22:32 and 13:23:00, all with the same
`processImage+1308` signature. Immediately before the 13:23:00 crash, the
composer logged `src ionImport is failed: Bad file descriptor(-1), ion_fd(-1)`
and `src ion mmap fail`. This supplies direct evidence of a failed buffer
import/mapping before that crash, without establishing why the descriptor
was invalid or proving that the helper removal caused it.

The removal experiment was reverted in source and a helper-restored rollback
image prepared. Do not use the no-wake comparison image for normal operation.
Restoring the helper returns to the previous configuration; it is not a fix
for the original first-lock crash. Regression logs are retained locally in
`build/no-wake-regression-20261027-1323/`.

After flashing the helper-restored image, the user confirmed the earlier
behavior returned: one crash on the first lock, then normal operation rather
than repeated crashes. Read-only inspection verified the helper is installed;
the crash buffer records the same composer `processImage+1308` SIGSEGV at
13:29:27.275. Evidence is local in
`build/wake-restored-crash-20261027-1329/`. Restoring the helper therefore
did not resolve the original first-lock failure. The next isolation test is
a boot with Eink Accessibility Service temporarily disabled, preserving all init display
fixes, to distinguish app-triggered display changes from the underlying
vendor sleep-transition path. This test has not yet been performed.

An attempted Eink Settings isolation test at 13:31–13:33 was **inconclusive**. Android
rejected a component-level shell disable. A package-level `pm disable-user`
initially succeeded, but did not remain effective through reboot: the app's process
started at 13:31:57 and its accessibility service connected at 13:32:07,
applying refresh, brightness and display settings before the reported first-lock
crash at 13:32:38.465. Post-crash package state was already `enabled=0`
(default), and accessibility was bound. The cause of the enablement reset is
not established. The package was explicitly returned to its original default
state and its accessibility binding verified. This run does **not** exclude
Eink Settings as a contributor. Evidence was retained in the original
disabled-app first-lock investigation directory from 2026-10-27.

A second attempt cleared enabled accessibility services after boot while the
phone was still locked. Dumps verified `Bound services:{}`,
`Enabled services:{}` and `deviceLocked=1` before the user unlocked. First lock
again produced the same composer crash at 13:36:18.624. However, the post-crash
snapshot already showed Eink Accessibility Service enabled and bound again. The app's boot receiver can
enable accessibility on `BOOT_COMPLETED`, which may arrive after first unlock;
retained logs do not establish whether re-enablement preceded the crash or
followed framework recovery. This test therefore also cannot exclude Eink Settings.
Saved accessibility settings were restored and binding verified. Evidence is
local in the original unbound-service first-lock investigation directory
from 2026-10-27. A better runtime isolation
requires disabling and verifying accessibility **after first unlock and before
first lock**, not before unlock.

To investigate a recurrence, connect USB and collect diagnostics before
holding Power. `adb get-state`, uptime, boot completion, `dumpsys power`, and
shutdown logs distinguish sleep from Android shutdown. If ADB disappears,
that alone does not prove power loss (USB/adbd may also fail); capture the next
boot reason and, with suitable authorized root, pstore/last-kmsg if available.
Pstore was not readable by the normal ADB shell on this build.
