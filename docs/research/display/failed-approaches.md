# What did not work / what not to repeat blindly

1. **HiBreak Pro Color HWC shim on this black-and-white device:** enlarged,
   cropped, banded output. Restoring stock vendor fixed geometry. The
   attempted passthrough switch did not disable its FD rewrite. Do not ship
   these experimental vendor images as the recommended solution.
2. **Blind HWC stride changes:** the RGBA pitch was consistent; successful
   EINK ioctl return codes did not establish correct panel output.
3. **EROFS GSIs:** the tested kernel lacks the required support; use ext4.
4. **Hisense A9 image patcher unchanged:** Qualcomm paths, model/density
   spoofing, framework modifications, and unverified policy changes do not
   form a safe HiBreak patch. Missing tools/labels also broke an attempted run.
5. **`adb root` as the fix:** hung or was unavailable on tested builds;
   `su 0` worked only on the separate SU diagnostic build. Root init helpers
   solved the rootless EvoX case.
6. **Wiping from fastbootd:** did not find userdata/metadata in this setup;
   an intentional factory reset worked from bootloader fastboot. Never wipe
   as part of an ordinary same-ROM patched-image update.
7. **Using mtkclient to flash `system_a`:** it is a dynamic logical partition
   inside super, not a standalone GPT partition. Use fastbootd for this task.
8. **Assuming a stock fallback slot protects data:** userdata is shared. Earlier
   slot A also had mismatched boot/dtbo after an incomplete OTA; this was a
   device-specific recovery issue, not a reason to copy boot images blindly.
