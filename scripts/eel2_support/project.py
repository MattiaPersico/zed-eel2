"""Bounded, read-only discovery of EEL2 source in explicit LSP workspace folders."""

import fnmatch
import os
from pathlib import Path

SOURCE_SUFFIXES = {'.jsfx', '.jsfx-inc', '.eel', '.eel2'}
EXCLUDED = {'node_modules', 'target', 'dist', 'build', 'vendor', '__pycache__'}
MAX_FILES = 256
MAX_ENTRIES = 8192
MAX_BYTES = 16 * 1024 * 1024
MAX_DEPTH = 16


def discover(workspace):
    documents, seen = [], set()
    count, size = 0, 0
    complete = True
    for root in workspace.roots:
        pending = [(root, 0)]
        while pending:
            directory, depth = pending.pop()
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        count += 1
                        if count > MAX_ENTRIES:
                            return documents, False
                        relative = Path(entry.path).relative_to(root).as_posix()
                        if entry.name.startswith('.') or entry.name in EXCLUDED or entry.is_symlink():
                            continue
                        if any(fnmatch.fnmatchcase(relative, pattern) or
                               fnmatch.fnmatchcase(relative + '/', pattern)
                               for pattern in workspace.excludes):
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if depth >= MAX_DEPTH:
                                complete = False
                            else:
                                pending.append((Path(entry.path), depth + 1))
                        elif entry.is_file(follow_symlinks=False) and Path(entry.name).suffix.lower() in SOURCE_SUFFIXES:
                            uri = Path(entry.path).resolve().as_uri()
                            if uri in seen:
                                continue
                            seen.add(uri)
                            if len(seen) > MAX_FILES:
                                return documents, False
                            file_size = entry.stat(follow_symlinks=False).st_size
                            size += file_size
                            if size > MAX_BYTES:
                                return documents, False
                            if file_size > workspace.MAX_FILE:
                                complete = False
                                continue
                            document = workspace.read(uri)
                            if document is None:
                                complete = False
                            else:
                                documents.append(document)
            except (OSError, ValueError):
                complete = False
    return documents, complete
