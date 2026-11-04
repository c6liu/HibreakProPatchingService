# Experimental: restore Bigme graphics-property access

Version 2 of this opt-in experiment targets four observed denied properties:
`vendor.xrz.fps_limit`, `vendor.xrz.gray_256_dither`, and
`vendor.xrz.hwc_idle`, plus `ro.vendor.xrz.screen_type`. It does not relabel
the rest of `vendor.xrz.*` or `ro.vendor.xrz.*`, change
vendor, add a new driver, or disable SELinux. It may affect display behavior;
**it has not been tested on the phone and is not a proven fix for the native
composer crash.** Keep the previous system image and a complete backup for
recovery. See [the policy comparison](../research/display/xrz-graphics-policy.md)
for evidence and limitations.

The tool requires a raw GSI system image, the raw stock vendor image matching
the target phone, host `secilc`, and the **SETools Python bindings** available
to the `python3` running the tool (`python3 -c 'import setools'`). It currently
accepts vendor policy version `31.0` only. That version check and a successful
preflight do not prove the backup matches the installed firmware. The
stock 3.1.6/EvoX 11.11 host combination was inspected; other GSIs or firmware
need separate validation.

Apply this **after** the display patcher and, if used, the IR overlay. Use the
same GSI build already installed on the test phone to make the experiment
comparable. Start from the **pre-XRZ image**, not the v1 or v2 XRZ output;
both versions are rejected as inputs. The stock composer obtains screen type
from a kernel ioctl and publishes it at startup. The overlay permits this
existing write; it does not supply a guessed panel value or set the read-only
property from init. Because it is `ro.*`, a normal boot after flashing is needed
to exercise that startup write; do not restart the composer to test it.
The tool preserves existing effective SELinux `allow` permissions
on the four properties and checks that the only additional effective `allow`
is the stock composer's property-service `set`. It rejects unexpected grants,
conditional rules it cannot safely compare, new neverallow violations, and
incompatible property contexts. Existing base GSI/vendor neverallow
violations are reported, not fixed; Android's runtime-style compilation uses
`-N` as in the IR preflight.

```bash
export XRZ_SOURCE=/path/to/current-system-image.img
export VENDOR=/path/to/matching-stock-vendor.img
export SECILC=/path/to/secilc
export XRZ_IMAGE=build/HiBreakPro-xrz-v2-test.img

# Validates the policy and property context; does not create an image.
python3 tools/add-xrz-compat-to-gsi.py "$XRZ_SOURCE" "$XRZ_IMAGE" \
  --vendor-image "$VENDOR" --secilc "$SECILC" --check-only

# Creates a separate image only after preflight. Existing outputs are refused.
python3 tools/add-xrz-compat-to-gsi.py "$XRZ_SOURCE" "$XRZ_IMAGE" \
  --vendor-image "$VENDOR" --secilc "$SECILC"
sha256sum "$XRZ_IMAGE"
```

The tool never flashes or accesses a phone. It copies the system image and
changes its platform policy, 31.0 mapping, property contexts, and policy-cache
digest; it reads but does not include or modify vendor. Follow the [flashing reference](../reference/flashing.md) and
the [same-GSI update instructions](../install/update.md) if you
choose to test it. An ordinary update to the **same** prepared GSI does not
need a data wipe, logical-partition deletion, or another vbmeta flash.

Collect comparable logs before and after the update, using separate new output
directories. The diagnostics can contain personal data; review before sharing:

```bash
D=build/xrz-before  # use build/xrz-after for the second capture
tools/collect-diagnostics.sh "$D"
adb shell getenforce > "$D/selinux-mode.txt"
adb logcat -d -b all -v threadtime > "$D/logcat-all.txt"
adb logcat -d -b crash -v threadtime > "$D/logcat-crash.txt"
adb shell dumpsys dropbox --print SYSTEM_RESTART > "$D/system-restarts.txt"
```

Confirm SELinux is enforcing, compare the four property-set failures and any
new AVCs, then exercise the same first unlock, sleep/wake, and scrolling
scenarios. Missing denials alone do not prove that the properties were written:
the writes may not have occurred or logs may have been rate-limited. Host
policy checks also cannot prove that the device selected the intended
contexts, or that its display behavior and stability improved.
