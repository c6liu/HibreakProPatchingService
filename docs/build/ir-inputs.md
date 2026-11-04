# Prepare IR build inputs

Skip this page if you do not want IR. The IR overlay needs a
**raw ext4 vendor image from your stock 3.1.6 backup** to validate policy.
It reads this file; it does not flash or modify vendor.

**Is this file required?** Yes for the IR overlay, including `--check-only`;
no for the display-only patcher. It supplies the vendor SELinux policy
and mapping version for the merge check, and the stock IR module/service
used to check the expected integration.

**It must match the vendor firmware installed on the target phone**, not
just its model. A backup from before a stock firmware update may no longer
match. The tool cannot compare an offline file with the recipient's phone.
Passing preflight proves only the checked inputs, not compatibility with
older/newer firmware, the kernel, or the physical device. Rebuilding with
another version's vendor is not by itself a supported port.

If vendor is stored inside the backup's `super.bin`, extract `vendor_a`
from it using a verified `lpunpack` tool. AOSP documents the
[dynamic-partition tools](https://android.googlesource.com/platform/system/extras/+/refs/tags/android-12.0.0_r1/partition_tools/).
Use a package from your distribution's signed repositories, if available,
or a tool built from a reviewed, pinned AOSP revision. Do not download
an arbitrary executable or clone a third-party default branch and immediately
run its script. A local extraction program can access your other files,
including signing keys; "runs locally" does not make untrusted code safe.

This guide does not supply a verified standalone extractor. If your backup
contains only `super.bin` and you cannot establish the tool's provenance,
stop here and get help preparing the vendor image, or continue with a
display-only build. Do not upload your firmware backup to an online extractor.
Keep the original backup unchanged and extract a working copy without root.

If your backup already contains a separate raw vendor image, use that
instead. Do not rename a complete `super.bin` to `vendor_a.img`.
Set `VENDOR` to the actual verified raw vendor file (replace this example
path), then check it:

```bash
export VENDOR="/path/to/extracted-vendor/vendor_a.img"
ls -lh "$VENDOR"
debugfs -R "cat /etc/selinux/plat_sepolicy_vers.txt" "$VENDOR"
```

The last command must read a policy version, not an invalid-filesystem
error. Extraction alone does not prove the backup matches your firmware.
If extraction fails or the partition is absent, stop and inspect your
backup/tool instructions rather than substituting another firmware's vendor.

## IR only: download the public HAL headers

The NDK provides Android system libraries but omits the legacy Consumer IR
HAL headers. Get the Android 12 public headers from Google's AOSP source;
do not download a proprietary replacement HAL or invent ABI declarations.
These two shallow source checkouts and three symlinks provide the includes:

```bash
git clone --depth 1 --branch android-12.0.0_r1 \
  https://android.googlesource.com/platform/hardware/libhardware \
  local/aosp-libhardware
git clone --depth 1 --branch android-12.0.0_r1 \
  https://android.googlesource.com/platform/system/core \
  local/aosp-system-core
mkdir -p local/ir-hal-headers
ln -s ../aosp-libhardware/include/hardware local/ir-hal-headers/hardware
ln -s ../aosp-system-core/libcutils/include/cutils local/ir-hal-headers/cutils
ln -s ../aosp-system-core/libsystem/include/system local/ir-hal-headers/system
export AOSP_HEADERS="$PWD/local/ir-hal-headers"
```

If you already prepared these headers, skip cloning/linking and set only
`AOSP_HEADERS`. Do not overwrite an existing working header directory.
The headers include the graphics/native-handle declarations transitively;
the full include directories above preserve those dependencies.
