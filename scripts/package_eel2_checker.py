#!/usr/bin/env python3
"""Package the optional native checker and its license notices; never effect sources."""
import argparse
import hashlib
from pathlib import Path
import zipfile
from package_eel2 import EXTENSION, version


def build(binary, ysfx, output):
    sources = [(binary, 'eel2-check.exe' if binary.suffix == '.exe' else 'eel2-check'),
               (EXTENSION / 'LICENSE', 'licenses/extension-MIT.txt')]
    for original, label in [('LICENSE', 'ysfx-Apache-2.0.txt'),
                            ('thirdparty/WDL/LICENSE.txt', 'WDL.txt'),
                            ('thirdparty/dr_libs/LICENSE', 'dr_libs.txt'),
                            ('thirdparty/stb/LICENSE', 'stb.txt'),
                            ('sources/eel2-gas/LICENSE.txt', 'eel2-gas.txt'),
                            ('sources/base64/Base64.hpp', 'Base64-source-and-notices.hpp')]:
        sources.append((ysfx / original, 'licenses/' + label))
    for source, _ in sources:
        if source.is_symlink() or not source.is_file():
            raise ValueError('Missing or symlinked compiler package input: ' + str(source))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream, zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        for source, label in sources:
            archive.write(source, label)
        archive.writestr('VERSION.txt', 'EEL2 checker ' + version() + '\nysfx 8077347ccf4115567aed81400281dca57acbb0cc\n')
    print(hashlib.sha256(output.read_bytes()).hexdigest() + '  ' + str(output))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--ysfx', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.binary, args.ysfx, args.output)
