#!/usr/bin/env python3
"""Remove explicitly marked diagnostic init blocks for release images."""

import re
import sys
from pathlib import Path


def remove_release_blocks(text: str, expected: tuple[str, ...], source: str) -> str:
    for name in expected:
        pattern = re.compile(
            rf"(?m)^# HIBREAK-RELEASE-REMOVE-BEGIN: {re.escape(name)}\n"
            rf".*?^# HIBREAK-RELEASE-REMOVE-END: {re.escape(name)}\n?",
            re.S,
        )
        text, removed = pattern.subn("", text)
        if removed != 1:
            raise ValueError(f"Expected exactly one release-removal block {name!r} in {source}")
    return text


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("Usage: prepare-release-init.py <display.rc> <eink.rc> <output-dir>")
    display_path, eink_path, output_dir = map(Path, sys.argv[1:])
    display = remove_release_blocks(
        display_path.read_text(),
        ("disable-hwc-diagnostic", "restart-surfaceflinger-diagnostic"),
        str(display_path),
    )
    eink = remove_release_blocks(
        eink_path.read_text(), ("eink-diagnostics",), str(eink_path),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "hibreak-display-release.rc").write_text(display)
    (output_dir / "eink_gsi-release.rc").write_text(eink)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit(str(error))
