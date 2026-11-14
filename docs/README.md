# Documentation

Pages are grouped by who needs them. Most users only need **install/**.

| Folder | Audience | Contents |
|--------|----------|----------|
| [install/](install) | Anyone installing or updating | Step-by-step install, update and recovery |
| [build/](build/README.md) | People building their own image | Host setup, inputs, signing, image build, optional overlays, tests |
| [reference/](reference) | Developers and maintainers | What the tools change and how the components behave |
| [research/](research/README.md) | Investigators | Dated evidence, experiments, crash analyses and IR reverse engineering |

## install/ — install a prebuilt image

Start from the [Guide](../Guide.md), which lists these in order.

- [prepare-computer.md](install/prepare-computer.md) — host packages, command rules, clone
- [download-release.md](install/download-release.md) — pick, verify and extract a release
- [backup-stock.md](install/backup-stock.md) — mtkclient stock backup
- [unlock-bootloader.md](install/unlock-bootloader.md)
- [first-install.md](install/first-install.md) — vbmeta, fastbootd, destructive first flash
- [first-boot-setup.md](install/first-boot-setup.md) — Eink Settings and IR use
- [update.md](install/update.md) — same-GSI, no-wipe update
- [switch-gsi.md](install/switch-gsi.md) — change GSI family (wipes data)
- [troubleshooting.md](install/troubleshooting.md) — common errors, returning to stock

## build/ — build an image from source

Overview and order: [build/README.md](build/README.md).

## reference/ — how things work

- [tested-baseline.md](reference/tested-baseline.md) — supported firmware/GSI inputs and scope
- [app-and-daemon.md](reference/app-and-daemon.md) — APK changes, controls, sysfs paths, limitations
- [settings.md](reference/settings.md) — user-visible button, refresh, popup and AOD settings
- [tools.md](reference/tools.md) — repository scripts and safety notes
- [patcher.md](reference/patcher.md) — `patch-gsi.sh` options, ADB/USB/root defaults, release mode
- [flashing.md](reference/flashing.md) — `flash-system.sh` behavior and flash errors
- [verification.md](reference/verification.md) — post-install checks and APK override fixes
- [display.md](reference/display.md) — hardware facts and the working display recipe
- [refresh-modes.md](reference/refresh-modes.md) — stock refresh constants and mode mapping
- [aod.md](reference/aod.md) — Always-On Display and inversion
- [ir-adapter.md](reference/ir-adapter.md) — Android IR adapter design and NEC contract

## research/ — evidence and investigations

See [research/README.md](research/README.md). These pages record dated
observations; current conclusions are summarized in the reference pages.
