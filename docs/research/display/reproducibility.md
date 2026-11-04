# Reproducibility and script locations

The working display scripts now live under [tools/display](../../../tools/display).
[patch-gsi.sh](../../../tools/patch-gsi.sh) replaces the external display patcher and
the session-only image updater scripts. [build-apk.sh](../../../tools/build-apk.sh)
and [patch-apk.py](../../../tools/patch-apk.py) include the previously manual
standalone, five-mode, toolbar and AOD-switch edits. The NDK build has its own
checked-in wrapper. No session-state directory or hard-coded home is required.

Large binaries/tools are user-supplied inputs, not source-controlled payloads.
Local copies are in ignored `local/`; new builds and diagnostics are in
ignored `build/`. Original external copies are retained as historical backups,
not required by any current tool. Experimental third-party shim sources and
stock firmware backups are deliberately not copied into the supported path.

Validation: full APK decode/patch/rebuild/sign, strict NDK compile, synthetic
ext4 integration tests, and a complete original-EvoX-to-patched-image run.
The resulting image passed `e2fsck` and embedded-file verification.
The consolidated image and its wake-only default have **not been flashed**.

## References

- [vbbot's 20250507 release](https://github.com/vbbot/HibreakProPatchingService/releases/tag/20250507)
- [Original GSI notes](https://vbh.ai/hibreak-pro-gsi-release/)
- [Original Android 15 guide](https://vbh.ai/hibreak-pro-guide-4-flashing-the-android-15-gsi/)
- [EvoX Treble](https://github.com/Doze-off/EvoX_treble/releases)
- [LineageOS for microG GSI](https://sourceforge.net/projects/lineageos-4-microg/files/GSI/16/)
- [HiBreak Pro XDA discussion](https://xdaforums.com/t/bigme-hibreak-pro-dimensity-900-mt6877-e-ink-phone.4723924/)
- [Pro Color shim research (not recommended for this baseline)](https://github.com/awong-dev/hibreak-pro-color)
