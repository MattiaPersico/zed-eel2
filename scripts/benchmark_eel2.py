#!/usr/bin/env python3
"""Report EEL2 editor latency on generated input; no audio or private files."""
import io
import json
from pathlib import Path
import statistics
import tempfile
import time

from eel2_support.language import Document, Workspace
from eel2_support.server import Server


def measure(operation):
    samples = []
    for _ in range(5):
        start = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - start) * 1000)
    return round(statistics.median(samples), 2)


def main():
    source = '@init\n' + ''.join('value%d = sin(%d);\n' % (i, i) for i in range(10000))
    with tempfile.TemporaryDirectory(prefix='eel2 benchmark ') as directory:
        root = Path(directory).resolve()
        uri = (root / 'large.jsfx').as_uri()
        workspace = Workspace()
        for i in range(40):
            (root / ('lib%d.jsfx-inc' % i)).write_text('function helper%d(x) (x);' % i, encoding='utf-8')
        imports = ''.join('import lib%d.jsfx-inc\n' % i for i in range(40))
        document = workspace.open(uri, imports + source + '\n@sample\nhelper', 1)
        server = Server(io.BytesIO())
        server.handle(dict(id=1, method='initialize', params={}))
        for i in range(20):
            other_uri = (root / ('open%d.jsfx' % i)).as_uri()
            server.workspace.open(other_uri, imports + '@sample\nspl0=0;', 1)
            workspace.open(other_uri, imports + '@sample\nhelper0(1);', 1)
        server.workspace.open(uri, source, 1)
        version = [1]
        def edit():
            version[0] += 1
            server.handle(dict(method='textDocument/didChange', params=dict(
                textDocument=dict(uri=uri, version=version[0]), contentChanges=[dict(text=source)])))
        print(json.dumps(dict(lines=10000, bytes=len(source.encode()), imports=40, open_documents=21,
            parse_ms=measure(lambda: Document(uri, source)),
            completion_ms=measure(lambda: workspace.completion(document, len(document.text))),
            references_ms=measure(lambda: workspace.references(document, document.text.index('value0'))),
            highlights_ms=measure(lambda: workspace.highlights(document, document.text.index("value0"))),
            workspace_symbols_ms=measure(lambda: workspace.workspace_symbols("helper")),
            edit_ms=measure(edit)), indent=2))


if __name__ == '__main__':
    main()
