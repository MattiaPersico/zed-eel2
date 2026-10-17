#!/usr/bin/env python3
"""Build the portable EEL2 server download using only the standard library."""

import argparse
import hashlib
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT if (ROOT / "extension.toml").is_file() else ROOT / "tools/zed-eel2"


def version():
    manifest = (EXTENSION / "extension.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "(\d+\.\d+\.\d+)"$', manifest, re.M)
    if not match:
        raise ValueError("Expected a semantic version in extension.toml")
    return match[1]


def build(output):
    """Refuse overwrites and package an explicit allowlist, never effect sources."""
    sources = [(ROOT / "scripts/eel2_lsp.py", "__main__.py"),
               (EXTENSION / "LICENSE", "LICENSE")]
    sources.extend((ROOT / "scripts/eel2_support" / name, "eel2_support/" + name)
                   for name in ("__init__.py", "catalog.py", "language.py", "server.py"))
    for path, _ in sources:
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing or symlinked release source: " + str(path))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
            for path, name in sorted(sources, key=lambda item: item[1]):
                info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / "dist" / ("eel2-lsp-v" + version() + ".pyz")
    if not output.is_absolute():
        output = ROOT / output
    try:
        digest = build(output)
    except (OSError, ValueError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(digest + "  " + str(output))


if __name__ == "__main__":
    main()
