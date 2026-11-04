# Download and check a prebuilt release

Download a **patched image from this repository's Releases**, not an upstream
GSI or the old vbbot APK-source image. You do not need the NDK, APK tools,
a signing key, or a separately extracted vendor image to install a prebuilt
release. You still need your own stock backup, the correct installed vendor
baseline, and an unlocked bootloader.

Open **Releases** on this repository's GitHub page and select the release
you intend to install. Read its release notes for compatibility and test
status, expand **Assets**, and save the release ZIP asset in `~/Downloads/`.
Do not download GitHub's automatic **Source code** archives. Each release
may use a different asset filename and checksum; use the values for the
specific release you selected, never values copied from an older release.
The stock **3.1.6 / `Bigme_HiBreak_V1.0_20260306`** restriction and known
limitations in the [Guide](../../Guide.md) still apply. Availability of an asset
is not proof that another firmware baseline is supported.

Check the downloaded **ZIP**, before extracting:

```bash
cd "$HOME/Downloads"
ZIP='REPLACE_WITH_EXACT_RELEASE_ASSET_FILENAME.zip'
SHA256='REPLACE_WITH_GITHUB_REPORTED_ASSET_SHA256'
printf '%s  %s\n' "$SHA256" "$ZIP" | sha256sum -c -
```

Expect `OK`. This checks the ZIP asset, not the extracted image. Stop on a
mismatch. Do not reuse a checksum from another release; if you cannot obtain
a verified digest for the selected asset, stop rather than treating an
unverified value as a successful check.

Inspect the archive contents, then extract without overwriting existing files:

```bash
cd "$HOME/HibreakProPatchingService"
ZIP='REPLACE_WITH_EXACT_RELEASE_ASSET_FILENAME.zip'
RELEASE_TAG='REPLACE_WITH_RELEASE_TAG'
unzip -l "$HOME/Downloads/$ZIP"
unzip -n "$HOME/Downloads/$ZIP" \
  -d "build/release-$RELEASE_TAG"
```

Set `IMAGE` to the extracted **system `.img`**, replacing the example
filename below with the actual path shown in the archive. Do not select
a ZIP, `boot`, `vendor`, or `super` image. If the system image is itself
compressed, extract it first. The flashing helper requires raw ext4:

```bash
export IMAGE="$PWD/build/release-REPLACE_WITH_RELEASE_TAG/REPLACE_WITH_SYSTEM_IMAGE_FILENAME.img"
ls -lh "$IMAGE"
e2fsck -fn "$IMAGE"
sha256sum "$IMAGE"
```

Stop if extraction or the filesystem check fails. If the release supplies
an explicitly identified raw-image checksum, compare it with this output
as well. Do not run the patcher or add IR again to an already patched image.
Keep `IMAGE` set in the terminal used for flashing; set it again if you open
a new terminal.

**First migration from stock:** [back up](backup-stock.md),
[unlock](unlock-bootloader.md) if needed, then follow
[First install](first-install.md) and [First-boot setup](first-boot-setup.md).
**Already running the same GSI:** use [Updating](update.md).
**Changing GSI families:** use [Switching GSIs](switch-gsi.md), which wipes
userdata; do not treat a change of GSI as a no-wipe update.
