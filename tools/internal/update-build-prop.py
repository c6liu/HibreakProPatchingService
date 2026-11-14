#!/usr/bin/env python3
"""Set USB, ADB and native-brightness slider defaults in one GSI build.prop."""

import sys
from pathlib import Path


def update_build_prop(path: Path, partition: str) -> None:
    lines = path.read_text().splitlines(keepends=True)
    for key, value in (
        ("persist.sys.usb.config", "mtp"),
        ("ro.adb.secure", "1"),
        ("sys.brightness.disable_gamma_conversion", "true"),
    ):
        indices = [index for index, line in enumerate(lines) if line.startswith(key + "=")]
        if len(indices) > 1:
            raise ValueError(f"Duplicate {key} entries in {partition}")
        if indices:
            lines[indices[0]] = f"{key}={value}\n"
        elif (
            key in ("persist.sys.usb.config", "sys.brightness.disable_gamma_conversion")
            and partition == "system/build.prop"
        ):
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(f"{key}={value}\n")
    path.write_text("".join(lines))


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: update-build-prop.py <build.prop> <image-path>")
    try:
        update_build_prop(Path(sys.argv[1]), sys.argv[2])
    except (OSError, ValueError) as error:
        raise SystemExit(str(error))


if __name__ == "__main__":
    main()
