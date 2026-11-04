# Back up stock firmware

**Before unlocking**, copy personal files off the phone. A partition backup
with `--skip=userdata` does **not** back up your photos, apps or settings.

Use the original [mtkclient project](https://github.com/bkerler/mtkclient):

1. Follow its [Linux installation instructions](https://github.com/bkerler/mtkclient/blob/main/README-INSTALL.md),
   including Python dependencies, `libusb`, and USB/udev rules for your distro.
   Use its virtual-environment instructions; do not install Python packages
   into the system interpreter with `sudo pip`.
2. Read its [usage instructions](https://github.com/bkerler/mtkclient/blob/main/README-USAGE.md)
   and the device-specific [HiBreak Pro backup/unlock notes](https://vbh.ai/unlocking-the-bootloader-and-rooting-the-hibreak-pro/).
3. From the **mtkclient folder**, using its configured Python environment,
   run this read-only backup command, then connect the powered-off phone as
   those instructions describe:

```bash
python mtk.py rl hibreak-backup --skip=userdata
```

Keep the whole backup and copy it to another drive. Check that the command
completed without errors and that you have nonempty `vbmeta_a.bin`,
`vbmeta_system_a.bin`, `vbmeta_vendor_a.bin`, and the stock partition images.
If files are missing, stop; do not unlock or flash using someone else's backup.
The backup may be inside the mtkclient folder, not this project's folder.
