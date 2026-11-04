# Third-party app issues

- **Kindle cannot download books reliably.** Seen on patched EvoX 11.11 microG,
  patched LineageOS 23.2 microG, and (as reported) Evolution X 10.5
  (Android 15). Kindle 8.159 fails with `FILE_SYSTEM_WRITE_ERROR`; logs show
  `EACCES` when it creates files under
  `/storage/emulated/0/Android/data/com.amazon.kindle/files/` (for example
  `kindle/*.ast_temp`), `statvfs` returning `EACCES`, and failure creating
  `/storage/emulated/0/Books/`. On LineageOS, one or a few downloads succeed
  after each reboot, then writes fail; restarting Kindle does not help, but
  rebooting does, temporarily. Free space was ample (221 GB).
  Visible ownership was correct (Kindle's UID, group 1015), the shell could
  write the same paths, and no matching SELinux denial was found, but the
  audit log was overflowing. Reinstalling Kindle and deleting its external
  folder did not help on EvoX. Although `persist.sys.fuse=true` and
  `ro.sys.sdcardfs=0`, `Android/data` and `Android/obb` are sdcardfs bind
  mounts over FUSE. The stock 4.19 kernel supports sdcardfs but not FUSE BPF,
  and the Android 16 `vold` in both EvoX and LineageOS carries a TrebleDroid
  patch ("FUSE BPF unavailable and sdcardfs supported; forcing sdcardfs") that
  selects sdcardfs regardless of `external_storage.sdcardfs.enabled`.
  Earlier patcher builds set that property to `false`. It did not change the
  mount, and AOSP `vold` also uses it to choose FUSE-style group IDs, quota
  project IDs and ACLs for `Android/data` directories, which do not match the
  sdcardfs mount. The patcher no longer sets it; whether that helps is
  untested. Root (`/system/xbin/su`, `adb root`) was not available, so the
  underlying `/data/media` permissions were not inspected. A kernel update is
  not practical (pre-GKI 4.19, no public Bigme source).
- **Outlook.com login page stays blank** (seen on EvoX). The account preferred a passkey.
  Outlook called Android Credential Manager; Bitwarden (the selected provider)
  returned an empty response and Android dropped microG's hybrid entry
  ("Remote entry being dropped as it is not from the service configured by the
  OEM"), so no prompt or error appeared. Saving a passkey in the credential
  provider, or disabling it as passkey provider, are the workarounds. This is
  a credential-provider issue, not specific to EvoX.
