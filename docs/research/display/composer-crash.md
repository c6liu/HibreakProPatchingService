# Observed graphics crash and soft restart

**Symptom (user report, 2026-10-26):** the UI broke and Android soft-restarted
once while scrolling or opening an app in **Extreme** mode.

**Evidence** (crash log buffer and dropbox, collected right after the report):

- `06:32:56.836` `SIGSEGV` (`SEGV_MAPERR`, fault addr `0xffffffffffffffff`) in
  the stock vendor `android.hardware.graphics.composer@2.3-service`,
  thread `Dispatcher_0`. Backtrace:

  ```text
  #00 libc.so              __memcmp_aarch64+16
  #01 hwcomposer.mt6877.so OverlayEngine::processImage(OverlayPortParam*, CommitInfo*)+1308
  #02 hwcomposer.mt6877.so OverlayEngine::preProcessFrame(sp<FrameInfo>)+312
  #03 hwcomposer.mt6877.so OverlayEngine::triggerEink(sp<FrameInfo>)+124
  #04 hwcomposer.mt6877.so OverlayEngine::trigger(...)
  #05 hwcomposer.mt6877.so HWCDispatcher::PhyPostHandler::process(DispatcherJob*)+916
  ```

  `hwcomposer.mt6877.so` BuildId `8a5cbea66efcb94a1a6cfdb53a239598`.
- `06:32:57.671` a new zygote logged `boot_progress_start` at kernel uptime
  153 s (the kernel had booted at about 06:30:35), and a new system_server
  followed. Dropbox recorded `SYSTEM_RESTART` at `06:33:10`. This is a
  framework (soft) restart caused by the composer dying, not a phone reboot.
- After the restart, `dumpsys SurfaceFlinger` again reports
  `h/w composer disabled`. No `hibreak-display` log lines were retained, so the
  logs do not show which trigger reapplied it.
- Dropbox holds six earlier tombstones with the **same** `processImage+1308`
  frame (04:38–04:40 EDT the same day, during display setup). So this is a
  recurring vendor composer crash, not a one-off.
- Another `SYSTEM_RESTART` at 06:14:39 has no matching tombstone. Its logs were
  no longer available, so its cause is unknown.

**Not related:** every boot logs a `SIGABRT` tombstone for `/system/bin/init
second_stage` with process uptime 0 s (`do_exec` → `Service::ExecStart`). That
is a forked `exec` child from a GSI/vendor rc file, not PID 1. This project's
rc files contain no `exec`. It happens at every boot and did not cause the
soft restart.

**Interpretation:** the crash is inside Bigme's closed E-Ink path of the stock
composer (`triggerEink` → `processImage`). Disabling HW overlays does not take
the vendor composer out of panel output and does not prevent it. The user's
report of Extreme mode during scrolling is context, not proof of the trigger;
the evidence does not establish the trigger, frequency, or whether refresh
mode or AOD changes contribute. This is unresolved; do not describe the
configuration as fully stable.

To capture the next occurrence before the logs rotate:

```bash
D=build/crash-$(date +%Y%m%d-%H%M); mkdir -p "$D"
adb logcat -d -b crash -v threadtime > "$D/logcat-crash.txt"
adb logcat -d -b all -v threadtime > "$D/logcat-all.txt"
adb shell dumpsys dropbox --print SYSTEM_TOMBSTONE > "$D/dropbox-tombstones.txt"
adb shell dumpsys dropbox --print SYSTEM_RESTART > "$D/dropbox-system-restart.txt"
```

Note the refresh mode and what you were doing. The evidence for the
2026-10-26 06:32 crash is kept locally in `build/crash-20261026-0632/`
(`build/` is not committed).
