# Reproducibility and script locations

The working display scripts now live under [tools/display](../../../tools/display).
[patch-gsi.sh](../../../tools/image/patch-gsi.sh) replaces the external display patcher and
the session-only image updater scripts.
[build-source-apk.sh](../../../tools/build/build-source-apk.sh) builds the checked-in
Kotlin/resources. The former binary APK patcher and smali payloads have been
removed; historical binary-patching validation below does not validate the
current source build. The NDK build has its own
checked-in wrapper. No session-state directory or hard-coded home is required.

Large binaries/tools are user-supplied inputs, not source-controlled payloads.
Local copies are in ignored `local/`; new builds and diagnostics are in
ignored `build/`. Original external copies are retained as historical backups,
not required by any current tool. Experimental third-party shim sources and
stock firmware backups are deliberately not copied into the supported path.

## Recent build and migration evidence (2026-11-11)

The user reported that separate test images for the init e-ink bridge, the
enforcing daemon (after the Binder callback fix), and enforcing display/AOD
helpers worked. The reports did not include a complete regression matrix.
The [verification history](../../reference/verification.md#migration-investigation-history)
distinguishes the initial failures from the later reported results.

The default release builder now uses those migrations on the pinned EvoX
system and stock 3.1.6 vendor inputs. It prepares one private working ext4
image, compiles the intermediate policies needed for XRZ and frontlight
permission preservation, then validates the combined policy, file contents,
labels, permissions, and filesystem. `--strict-verification` retains the
per-stage checks; other feature combinations use per-stage verification.
The merged policy retains 386 existing assertion diagnostic blocks and
`phhsu_daemon` remains permissive.

On the tested host, a no-flash combined build using a previously signed APK
took about 106 seconds, compared with about 465 seconds for the previous
per-stage build. A strict build also completed. Comparison of 21 changed
files found matching contents, modes, owners and SELinux labels between the
combined and strict outputs; the removed files were absent. This comparison
does not prove device behavior or whole-image identity. A subsequent build
using the reorganized script paths also passed its host checks. No device was
flashed as part of these build comparisons.

Earlier work used APK decode/patch/rebuild/sign and produced a separate
consolidated wake-only image. Those historical binary-APK results do not
validate the current source-built APK or imply that particular image was
flashed. Current commands and signing instructions are in the
[build guide](../../build/build-image.md).

## References

- [vbbot's 20250507 release](https://github.com/vbbot/HibreakProPatchingService/releases/tag/20250507)
- [Original GSI notes](https://vbh.ai/hibreak-pro-gsi-release/)
- [Original Android 15 guide](https://vbh.ai/hibreak-pro-guide-4-flashing-the-android-15-gsi/)
- [EvoX Treble](https://github.com/Doze-off/EvoX_treble/releases)
- [LineageOS for microG GSI](https://sourceforge.net/projects/lineageos-4-microg/files/GSI/16/)
- [HiBreak Pro XDA discussion](https://xdaforums.com/t/bigme-hibreak-pro-dimensity-900-mt6877-e-ink-phone.4723924/)
- [Pro Color shim research (not recommended for this baseline)](https://github.com/awong-dev/hibreak-pro-color)
