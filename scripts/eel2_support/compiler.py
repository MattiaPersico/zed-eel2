"""Optional compile-only checker over isolated source snapshots, never effect execution."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from . import VERSION


def checker_path():
    configured = os.environ.get('EEL2_CHECKER')
    if configured is not None:
        path = Path(configured)
        return str(path) if configured and path.is_absolute() else None
    suffix = '.exe' if os.name == 'nt' else ''
    path = Path(sys.argv[0]).resolve().with_name('eel2-check-v' + VERSION + suffix)
    return str(path) if path.is_file() else None


def check(executable, workspace, document, sources):
    """Return diagnostics on the root; ambiguous import locations stay at line one."""
    def diagnostic(message, line=0, severity=1):
        line = max(0, min(line, len(document.starts) - 1))
        start = document.starts[line]
        return dict(range=document.range(start, start), severity=severity, source='eel2-ysfx', message=message)
    if any(d.preprocessed for d in sources):
        return [diagnostic('Compiler check skipped: preprocessing is not executed.', severity=3)]
    if not workspace.imports_complete(document):
        return [diagnostic('Compiler check skipped: local imports are missing or exceed the import limit.', severity=3)]
    if any(len(d.text.encode('utf-8')) > workspace.MAX_FILE for d in sources) or sum(len(d.text) for d in sources) > 16 * 1024 * 1024:
        return [diagnostic('Compiler snapshot exceeds the source size limit.', severity=3)]
    try:
        with tempfile.TemporaryDirectory(prefix='eel2-check-') as directory:
            root = Path(directory)
            names = {d.canonical_uri: 'source%03d.jsfx' % i for i, d in enumerate(sources)}
            for source in sources:
                text = source.text
                for name, token in reversed(source.imports):
                    uri = workspace.import_uri(source, name)
                    if uri not in names:
                        return [diagnostic('Compiler snapshot has an unresolved import.', severity=3)]
                    text = text[:token.start] + 'import ' + names[uri] + text[token.end:]
                (root / names[source.canonical_uri]).write_text(text, encoding='utf-8')
            result = subprocess.run([executable, str(root / names[document.canonical_uri])],
                                    cwd=directory, capture_output=True, timeout=5)
        if len(result.stdout) > 1024 * 1024:
            return [diagnostic('Compiler output exceeds the limit.', severity=2)]
        response = json.loads(result.stdout)
        if not isinstance(response, dict) or not isinstance(response.get('ok'), bool) or result.returncode not in (0, 1):
            raise ValueError('Invalid checker response')
        diagnostics = []
        for item in response.get('messages', [])[:100]:
            if item.get('level', 0) < 1:
                continue
            message = str(item.get('text', ''))[:8192]
            # ysfx compilation logs lack a source filename. Never assign an import
            # error to an unrelated root line; the full message remains visible.
            match = re.search(r'(?:line\s+|:\s*)(\d+)(?::|\b)', message, re.I)
            line = int(match[1]) - 1 if match and len(sources) == 1 else 0
            if len(sources) > 1:
                message = 'Import chain: ' + message
            diagnostics.append(diagnostic(message, line, 1 if item['level'] >= 2 else 2))
        if not response['ok'] and not diagnostics:
            diagnostics.append(diagnostic('ysfx rejected the source without an error message.'))
        return diagnostics
    except subprocess.TimeoutExpired:
        return [diagnostic('Compiler check stopped after 5 seconds.', severity=2)]
    except (OSError, UnicodeError, ValueError, TypeError, AttributeError) as error:
        return [diagnostic('Compiler check unavailable: ' + str(error)[:300], severity=2)]
