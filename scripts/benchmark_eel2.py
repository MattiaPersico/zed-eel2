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
from eel2_support.calls import prepare, calls


def measure(operation):
    samples = []
    for _ in range(5):
        start = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - start) * 1000)
    return round(statistics.median(samples), 2)


def disk_project(root):
    """Exercise real discovery and reads, including broad capped searches."""
    root.mkdir()
    for i in range(128):
        (root / ('effect%d.jsfx' % i)).write_text('@init\n' + ''.join(
            'function filter_%d_%d(x) (x);\n' % (i, j) for j in range(100)), encoding='utf-8')
    workspace = Workspace()
    workspace.set_folders([root.as_uri()])
    start = time.perf_counter()
    workspace.workspace_symbols('filter')
    cold = round((time.perf_counter() - start) * 1000, 2)
    broad = measure(lambda: workspace.workspace_symbols('filter'))
    narrow = measure(lambda: workspace.workspace_symbols('filter_127_99'))
    path = root / 'effect127.jsfx'
    path.write_text('@init\nfunction changed_filter(x) (x);', encoding='utf-8')
    # Notification-driven invalidation is measured separately from fresh stat reads.
    workspace.invalidate_disk([path.as_uri()])
    start = time.perf_counter()
    result = workspace.workspace_symbols('changed_filter')
    changed = round((time.perf_counter() - start) * 1000, 2)
    assert len(result) == 1 and result[0]['name'] == 'changed_filter'
    return dict(files=128, symbols=12800, cold_search_ms=cold,
                warm_broad_search_ms=broad, warm_narrow_search_ms=narrow,
                search_after_one_file_change_ms=changed)


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
        helper = workspace.read((root / 'lib0.jsfx-inc').as_uri())
        hierarchy_item = prepare(workspace, helper, helper.text.index('helper0'))[0]
        assert len(calls(workspace, hierarchy_item, True)) == 20 and workspace.scan_complete
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
            incoming_calls_ms=measure(lambda: calls(workspace, hierarchy_item, True)),
            edit_ms=measure(edit), disk_project=disk_project(root / 'project')), indent=2))


if __name__ == '__main__':
    main()
