"""Static call hierarchy behavior, client protocol and bounded discovery."""
import copy
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from eel2_support.language import Workspace
from eel2_support.calls import prepare, calls, StaleItem
from eel2_support.server import Server, read_message


class CallHierarchyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='eel2 calls ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.workspace = Workspace()
        self.workspace.set_folders([self.root.as_uri()])

    def doc(self, text, name='effect.jsfx', opened=True):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode('utf-8'))
        return self.workspace.open(path.as_uri(), text, 1) if opened else self.workspace.read(path.as_uri())

    def prepared(self, doc, name):
        result = prepare(self.workspace, doc, doc.text.index(name))
        self.assertEqual(len(result), 1)
        return result[0]

    def slices(self, document, entry):
        return [document.text[document.offset(r['start']):document.offset(r['end'])]
                for r in entry['fromRanges']]

    def test_incoming_groups_functions_and_top_level_sections_with_precise_ranges(self):
        doc = self.doc('@init\r\nfunction leaf(x) (x);\r\n'
                       'function wrapper(x) (leaf(x)+leaf(x));\r\n'
                       '@sample\r\n"🎵"; a.leaf(1); leaf(2);\r\n@gfx 100 100\r\nleaf(3);')
        selected = self.prepared(doc, 'leaf(x)')
        self.assertEqual(selected['range']['start'], dict(line=1, character=0))
        incoming = calls(self.workspace, selected, True)
        self.assertEqual({r['from']['name'] for r in incoming}, {'wrapper', '@sample', '@gfx'})
        by_name = {r['from']['name']: r for r in incoming}
        self.assertEqual(self.slices(doc, by_name['wrapper']), ['leaf', 'leaf'])
        self.assertEqual(self.slices(doc, by_name['@sample']), ['a.leaf', 'leaf'])
        self.assertEqual(by_name['@sample']['fromRanges'][0]['start'], dict(line=4, character=6))
        for entry in incoming:
            self.assertEqual(calls(self.workspace, entry['from'], False)[0]['to']['name'], 'leaf')
        self.assertEqual(self.prepared(doc, '@sample')['name'], '@sample')

    def test_outgoing_imports_nested_calls_and_repeated_call_sites(self):
        library = self.doc('function helper(x) (x);', 'lib.jsfx-inc', False)
        doc = self.doc('import lib.jsfx-inc\n@init\nfunction wrapper(x) (helper(helper(x))+helper(2)+sin(x));')
        result = calls(self.workspace, self.prepared(doc, 'wrapper'), False)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['to']['uri'], library.uri)
        self.assertEqual(self.slices(doc, result[0]), ['helper', 'helper', 'helper'])
        self.assertEqual(self.prepared(doc, 'helper(helper')['name'], 'helper')
        self.assertEqual(prepare(self.workspace, doc, doc.text.index('sin(x)')), [])

    def test_unopened_callers_new_files_exclusions_and_unsaved_precedence(self):
        library = self.doc('function leaf(x) (x);', 'lib.jsfx-inc')
        caller = self.doc('import lib.jsfx-inc\n@sample\nleaf(1);', 'caller.jsfx', False)
        selected = self.prepared(library, 'leaf')
        self.assertEqual(calls(self.workspace, selected, True)[0]['from']['uri'], caller.uri)
        self.workspace.open(caller.uri, 'import lib.jsfx-inc\n@sample\nsin(1);', 2)
        self.doc('import ../lib.jsfx-inc\n@sample\nleaf(1);', 'vendor/ignored.jsfx', False)
        self.assertEqual(calls(self.workspace, selected, True), [])
        new = self.doc('import lib.jsfx-inc\n@sample\nleaf(2);', 'new.jsfx', False)
        self.assertEqual(calls(self.workspace, selected, True)[0]['from']['uri'], new.uri)
        (self.root / 'new.jsfx').unlink()
        self.assertEqual(calls(self.workspace, selected, True), [])

    def test_plain_eel_top_level_calls_have_expandable_file_items(self):
        doc = self.doc('function leaf(x) (x); leaf(1); leaf(2);', 'script.eel')
        selected = self.prepared(doc, 'leaf')
        incoming = calls(self.workspace, selected, True)
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0]['from']['name'], 'script.eel')
        self.assertEqual(self.slices(doc, incoming[0]), ['leaf', 'leaf'])
        self.assertEqual(calls(self.workspace, incoming[0]['from'], False)[0]['to']['name'], 'leaf')
        self.assertEqual(calls(self.workspace, incoming[0]['from'], True), [])

    def test_dynamic_ambiguous_preprocessed_calls_and_non_calls_are_omitted(self):
        doc = self.doc('@init\nfunction leaf(x) (x);\nfunction dynamic(ns*) (ns.leaf(1)+this.leaf(1));\n'
                       'function literal() (a.leaf(1));\n@sample\n"leaf(1)"; // leaf(1)\nleaf=2;')
        selected = self.prepared(doc, 'leaf(x)')
        self.assertEqual([r['from']['name'] for r in calls(self.workspace, selected, True)], ['literal'])
        self.assertEqual(prepare(self.workspace, doc, doc.text.index('ns.leaf')), [])
        self.assertEqual(prepare(self.workspace, doc, doc.text.index('leaf=2')), [])
        generated = self.doc('<? ?>\n@init\nfunction generated() (leaf(1));', 'generated.jsfx')
        self.assertEqual(prepare(self.workspace, generated, generated.text.index('generated')), [])
        self.doc('function leaf(x) (x);', 'one.jsfx-inc', False)
        self.doc('function leaf(x) (x);', 'two.jsfx-inc', False)
        ambiguous = self.doc('import one.jsfx-inc\nimport two.jsfx-inc\n@sample\nleaf(1);', 'ambiguous.jsfx')
        self.assertEqual(prepare(self.workspace, ambiguous, ambiguous.text.index('leaf(1)')), [])

    def test_shared_import_resolving_differently_in_effects_is_not_guessed(self):
        library = self.doc('function wrapper() (helper());', 'lib.jsfx-inc')
        for name in ('first.jsfx', 'second.jsfx'):
            self.doc('import lib.jsfx-inc\n@init\nfunction helper() (1);\n@sample\nwrapper();', name, False)
        self.assertEqual(calls(self.workspace, self.prepared(library, 'wrapper'), False), [])

    def test_sections_keep_same_named_functions_separate_and_skip_incomplete_sources(self):
        doc = self.doc('@init\nfunction leaf() (1);\nfunction wrapper() (leaf());\n'
                       '@sample\nfunction leaf() (2);\nleaf();')
        first = self.prepared(doc, 'leaf() (1)')
        second = self.prepared(doc, 'leaf() (2)')
        self.assertEqual([r['from']['name'] for r in calls(self.workspace, first, True)], ['wrapper'])
        self.assertEqual([r['from']['name'] for r in calls(self.workspace, second, True)], ['@sample'])
        broken = self.doc('@init\nfunction broken() (1;', 'broken.jsfx', False)
        self.assertEqual(prepare(self.workspace, broken, broken.text.index('broken')), [])
        calls(self.workspace, first, True)
        self.assertFalse(self.workspace.scan_complete)

    def test_without_workspace_folders_only_open_buffers_and_imports_are_followed(self):
        self.workspace.set_folders([])
        library = self.doc('function leaf() (1);', 'lib.jsfx-inc', False)
        caller = self.doc('import lib.jsfx-inc\n@sample\nleaf();')
        self.doc('import lib.jsfx-inc\n@sample\nleaf();', 'unopened.jsfx', False)
        incoming = calls(self.workspace, self.prepared(library, 'leaf'), True)
        self.assertEqual([r['from']['uri'] for r in incoming], [caller.uri])

    def test_symlink_import_aliases_do_not_duplicate_call_sites(self):
        library = self.doc('function leaf() (1);', 'lib.jsfx-inc')
        alias = self.root / 'alias.jsfx-inc'
        try:
            alias.symlink_to(self.root / 'lib.jsfx-inc')
        except OSError as error:
            self.skipTest(str(error))
        caller = self.doc('import lib.jsfx-inc\nimport alias.jsfx-inc\n@sample\nleaf();')
        incoming = calls(self.workspace, self.prepared(library, 'leaf'), True)
        self.assertEqual(len(incoming), 1)
        self.assertEqual(self.slices(caller, incoming[0]), ['leaf'])

    def test_stale_items_are_rejected_and_reprepared_after_unsaved_changes(self):
        doc = self.doc('@init\nfunction leaf() (1);\n@sample\nleaf();')
        selected = self.prepared(doc, 'leaf')
        altered = copy.deepcopy(selected); altered['selectionRange']['start']['character'] += 1
        with self.assertRaises(StaleItem):
            calls(self.workspace, altered, True)
        changed = self.workspace.open(doc.uri, '// moved\n' + doc.text, 2)
        with self.assertRaises(StaleItem):
            calls(self.workspace, selected, True)
        self.assertEqual(len(calls(self.workspace, self.prepared(changed, 'leaf'), True)), 1)
        self.assertEqual(calls(self.workspace, {'uri':doc.uri, 'data':None}, True), [])

    def test_result_and_work_budgets_mark_incomplete_without_unbounded_graphs(self):
        doc = self.doc('@init\nfunction leaf() (1);\nfunction a() (leaf();leaf());\nfunction b() (leaf());')
        selected = self.prepared(doc, 'leaf')
        with patch('eel2_support.calls.MAX_RESULTS', 1):
            self.assertEqual(len(calls(self.workspace, selected, True)), 1)
            self.assertFalse(self.workspace.scan_complete)
        with patch('eel2_support.calls.MAX_RANGES', 1):
            self.assertEqual(len(calls(self.workspace, selected, True)[0]['fromRanges']), 1)
            self.assertFalse(self.workspace.scan_complete)
        for budget in ('MAX_TOKENS', 'MAX_CALL_SITES', 'MAX_RESOLUTIONS'):
            with patch('eel2_support.calls.' + budget, 1):
                self.assertEqual(calls(self.workspace, selected, True), [])
                self.assertFalse(self.workspace.scan_complete)
        self.assertEqual(len(calls(self.workspace, selected, True)), 2)
        self.assertTrue(self.workspace.scan_complete)

    def test_protocol_capability_directions_and_content_modified_response(self):
        doc = self.doc('@init\nfunction leaf() (1);\n@sample\nleaf();')
        out = io.BytesIO()
        with patch('eel2_support.server.checker_path', return_value=None):
            server = Server(out)
        server.handle(dict(id=1, method='initialize', params=dict(rootUri=self.root.as_uri())))
        server.handle(dict(method='textDocument/didOpen', params=dict(textDocument=dict(
            uri=doc.uri, text=doc.text, version=1))))
        server.handle(dict(id=2, method='textDocument/prepareCallHierarchy', params=dict(
            textDocument=dict(uri=doc.uri), position=doc.position(doc.text.index('leaf')))))
        out.seek(0); messages=[]
        while True:
            message=read_message(out)
            if message is None: break
            messages.append(message)
        self.assertTrue(messages[0]['result']['capabilities']['callHierarchyProvider'])
        selected=next(m for m in messages if m.get('id')==2)['result'][0]
        out.seek(0,2)
        server.handle(dict(id=3, method='callHierarchy/incomingCalls', params=dict(item=selected)))
        server.handle(dict(id=4, method='callHierarchy/outgoingCalls', params=dict(item=selected)))
        server.handle(dict(method='textDocument/didChange', params=dict(textDocument=dict(uri=doc.uri,version=2),
            contentChanges=[dict(text='// moved\n'+doc.text)])))
        server.handle(dict(id=5, method='callHierarchy/incomingCalls', params=dict(item=selected)))
        out.seek(0); messages=[]
        while True:
            message=read_message(out)
            if message is None: break
            messages.append(message)
        self.assertEqual(next(m for m in messages if m.get('id')==3)['result'][0]['from']['name'], '@sample')
        self.assertEqual(next(m for m in messages if m.get('id')==4)['result'], [])
        self.assertEqual(next(m for m in messages if m.get('id')==5)['error']['code'], -32801)
