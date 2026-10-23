"""Behavioral checks for workspace discovery, refactoring, formatting and compilation."""
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from eel2_support.language import Workspace, Document
from eel2_support.editing import EditError, prepare_rename, rename, format_document
from eel2_support.compiler import check
from eel2_support.server import Server, read_message


def apply_edits(document, edits):
    text = document.text
    for edit in sorted(edits, key=lambda e: document.offset(e['range']['start']), reverse=True):
        start, end = [document.offset(edit['range'][key]) for key in ('start', 'end')]
        text = text[:start] + edit['newText'] + text[end:]
    return text


class EditingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='eel2 editing ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.workspace = Workspace()
        self.workspace.set_folders([self.root.as_uri()])

    def doc(self, text, name='effect.jsfx', opened=True):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return self.workspace.open(path.as_uri(), text, 4) if opened else self.workspace.read(path.as_uri())

    def test_closed_importers_are_found_but_hidden_build_and_excluded_files_are_not(self):
        library = self.doc('function f(x) (x);', 'lib.jsfx-inc')
        closed = self.doc('import lib.jsfx-inc\n@sample\nf(1);', 'closed.jsfx', False)
        self.doc('import ../lib.jsfx-inc\n@sample\nf(1);', '.hidden/a.jsfx', False)
        self.doc('import ../lib.jsfx-inc\n@sample\nf(1);', 'build/a.jsfx', False)
        self.doc('import lib.jsfx-inc\n@sample\nf(1);', 'excluded.jsfx', False)
        self.workspace.excludes = ['excluded.jsfx']
        refs = self.workspace.references(library, 9)
        self.assertEqual([r['uri'] for r in refs], [closed.uri])
        with patch('eel2_support.project.MAX_FILES', 1):
            self.workspace.references(library, 9)
            self.assertFalse(self.workspace.scan_complete)
            with self.assertRaises(EditError):
                rename(self.workspace, library, 9, 'new_f')

    def test_symlink_directories_are_not_followed(self):
        external = self.root / '.hidden'
        external.mkdir()
        (external / 'effect.jsfx').write_text('@init\nx=1;')
        try:
            (self.root / 'linked').symlink_to(external, target_is_directory=True)
        except OSError as error:
            self.skipTest(str(error))
        from eel2_support.project import discover
        self.assertEqual(discover(self.workspace), ([], True))

    def test_function_rename_edits_closed_importers_and_keeps_versions(self):
        library = self.doc('function scale(x) (x);', 'lib.jsfx-inc')
        user = self.doc('import lib.jsfx-inc\n@sample\nspl0=scale(1);', 'caller.jsfx', False)
        result = rename(self.workspace, library, 10, 'amplify', True)
        versions = {c['textDocument']['uri']: c['textDocument']['version'] for c in result['documentChanges']}
        self.assertEqual(versions, {library.uri: 4, user.uri: None})
        for change in result['documentChanges']:
            doc = self.workspace.read(change['textDocument']['uri'])
            text = apply_edits(doc, change['edits'])
            self.assertIn('amplify(', text)
            self.assertNotIn('scale(', text)
        self.assertIn('scale(', Path(self.root / 'caller.jsfx').read_text())

    def test_local_rename_does_not_touch_globals_or_another_function(self):
        doc = self.doc('@init\nx=1; function f(x) (x); function g(x) (x);\n@sample\nx;')
        result = rename(self.workspace, doc, doc.text.index('x) (x)'), 'input')
        changed = apply_edits(doc, result['changes'][doc.uri])
        self.assertIn('function f(input) (input); function g(x) (x)', changed)
        self.assertIn('@sample\nx;', changed)
        self.assertEqual(len(result['changes'][doc.uri]), 2)

    def test_namespace_parameter_rename_changes_only_prefix(self):
        doc = self.doc('@init\nfunction copy(src*) (this.value=src.value; src.other);')
        result = rename(self.workspace, doc, doc.text.index('src*'), 'source')
        changed = apply_edits(doc, result['changes'][doc.uri])
        self.assertIn('copy(source*)', changed)
        self.assertIn('source.value', changed)
        self.assertIn('source.other', changed)
        self.assertIn('this.value', changed)
        self.assertIsNone(prepare_rename(self.workspace, doc, doc.text.index('src.value') + 4))

    def test_rename_rejects_capture_reserved_names_and_invalid_identifiers(self):
        doc = self.doc('@init\ny=1; function f(x) (x+y);')
        offset = doc.text.index('x)')
        for name in ('y', 'sin', 'this', 'slider1', 'a.b', '1x', '#str', ''):
            with self.subTest(name=name), self.assertRaises(EditError):
                rename(self.workspace, doc, offset, name)
        changed = rename(self.workspace, doc, offset, 'X')['changes'][doc.uri]
        self.assertEqual(len(changed), 2)
        self.assertIsNone(prepare_rename(self.workspace, doc, doc.text.index('function')))

    def test_rename_rejects_shared_globals_preprocessors_and_unresolved_imports(self):
        library = self.doc('function get() (value);', 'lib.jsfx-inc')
        doc = self.doc('import lib.jsfx-inc\n@init\nvalue=1;')
        self.doc('import lib.jsfx-inc\n@init\nvalue=2;', 'other.jsfx', False)
        with self.assertRaises(EditError):
            rename(self.workspace, doc, doc.text.index('value'), 'state')
        bad = self.doc('import missing.jsfx-inc\n@init\nfunction f() (1);', 'bad.jsfx')
        with self.assertRaises(EditError):
            rename(self.workspace, bad, bad.text.index('f()'), 'new_f')
        generated = self.doc('@init\n<? ?>\nx=1;', 'generated.jsfx')
        self.assertIsNone(prepare_rename(self.workspace, generated, generated.text.index('x=1')))

    def test_rename_rejects_ambiguous_calls_and_instance_namespace_changes(self):
        for body in ('function f() instance(x) (x=1); f();',
                     'function f() (this.x=1); f();',
                     'function f() (1); function f() (2); f();',
                     'function f() (1); function caller(src*) (src.f());'):
            doc = self.doc('@init\n' + body)
            with self.subTest(body=body), self.assertRaises(EditError):
                rename(self.workspace, doc, doc.text.index('f()'), 'renamed')

    def test_global_rename_preserves_slider_metadata_and_rejects_formatted_strings(self):
        doc = self.doc('desc:gain control\nslider1:gain=1<0,2>Gain\n@sample\nspl0*=gain;')
        changes = rename(self.workspace, doc, doc.text.index('gain=1'), 'level')['changes'][doc.uri]
        changed = apply_edits(doc, changes)
        self.assertIn('desc:gain control', changed)
        self.assertIn('slider1:level=1<0,2>Gain', changed)
        self.assertIn('spl0*=level', changed)
        doc = self.doc('@init\ngain=1; sprintf(#str,"%{gain}f");')
        with self.assertRaises(EditError):
            rename(self.workspace, doc, doc.text.index('gain'), 'level')

    def test_static_instance_references_link_methods_and_separate_objects(self):
        doc = self.doc('@init\nfunction set(x) instance(value) (value=x);\n'
                       'function get() (this.value);\n@sample\na.set(1); a.get(); b.set(2); a.value; b.value;')
        refs = self.workspace.references(doc, doc.text.index('a.value'), True)
        pieces = [doc.text[doc.offset(r['range']['start']):doc.offset(r['range']['end'])] for r in refs]
        self.assertEqual(pieces, ['value', 'value', 'value', 'a.value'])
        self.assertNotIn('b.value', pieces)

    def test_namespace_arguments_and_parent_paths_are_instantiated_without_execution(self):
        doc = self.doc('@init\nfunction copy(src*) (this.value=src.value; this..total=1);\n'
                       '@sample\na.b.copy(other); a.b.value; other.value; a.total;')
        for needle, expected in [('other.value;', 2), ('a.total;', 2), ('a.b.value;', 2)]:
            refs = self.workspace.references(doc, doc.text.index(needle), True)
            self.assertEqual(len(refs), expected)
        unknown = self.doc('@init\nfunction f(src*) (src.value);\n@sample\nf(1+2); other.value;')
        self.assertEqual(len(self.workspace.references(unknown, unknown.text.index('other.value'), True)), 1)

    def test_formatter_preserves_tokens_crlf_strings_comments_and_is_idempotent(self):
        source = 'desc: Keep  text  \r\nslider1:gain=1<0,2>Gain\r\n@init\r\nfunction f(x) (\r\nx ? (\r\ny=1;   \r\n) : (\r\ny=2;\r\n);\r\n"🎵\r\n  untouched string  ";\r\n/* comment\r\n  untouched comment */\r\n);\r\n'
        doc = self.doc(source)
        edits = format_document(doc, {'tabSize': 2, 'insertSpaces': True})
        formatted = apply_edits(doc, edits)
        result = Document(doc.uri, formatted)
        self.assertEqual([(t.kind,t.value) for t in doc.tokens], [(t.kind,t.value) for t in result.tokens])
        self.assertIn('\r\n    y=1;\r\n', formatted)
        self.assertIn('\r\n  ) : (\r\n', formatted)
        self.assertEqual(format_document(result, {'tabSize': 2}), [])
        tabs = apply_edits(doc, format_document(doc, {'tabSize': 4, 'insertSpaces': False}))
        self.assertIn('\r\n\t\ty=1;', tabs)

    def test_formatter_declines_incomplete_and_generated_source(self):
        for text in ('@init\nx=(1;', '@init\n<? ?>\nx=1;'):
            self.assertEqual(format_document(self.doc(text), {'tabSize': 2}), [])

    def test_protocol_folders_rename_and_formatting(self):
        out = io.BytesIO()
        with patch('eel2_support.server.checker_path', return_value=None):
            server = Server(out)
        server.handle(dict(id=1, method='initialize', params=dict(workspaceFolders=[dict(uri=self.root.as_uri())],
            capabilities=dict(workspace=dict(workspaceEdit=dict(documentChanges=True))))))
        doc = self.doc('@init\nfunction f(x) (\nx;\n);')
        server.workspace.open(doc.uri, doc.text, 8)
        position = doc.position(doc.text.index('x)'))
        for id_, method, params in [(2, 'textDocument/prepareRename', dict(position=position)),
                                   (3, 'textDocument/rename', dict(position=position,newName='input')),
                                   (4, 'textDocument/formatting', dict(options=dict(tabSize=2,insertSpaces=True)))]:
            server.handle(dict(id=id_, method=method, params=dict(textDocument=dict(uri=doc.uri), **params)))
        out.seek(0)
        read_message(out)
        self.assertEqual(read_message(out)['result']['placeholder'], 'x')
        self.assertEqual(read_message(out)['result']['documentChanges'][0]['textDocument']['version'], 8)
        self.assertTrue(read_message(out)['result'])
        server.handle(dict(method='workspace/didChangeWorkspaceFolders', params=dict(event=dict(
            removed=[dict(uri=self.root.as_uri())],added=[]))))
        self.assertEqual(server.workspace.roots, [])

    def test_compiler_worker_does_not_publish_stale_results_after_edit(self):
        started, release = threading.Event(), threading.Event()
        def slow_check(*args):
            started.set()
            release.wait(2)
            return [dict(range=dict(start=dict(line=0,character=0), end=dict(line=0,character=0)),
                         severity=1, source='eel2-ysfx', message='stale error')]
        output = io.BytesIO()
        with patch('eel2_support.server.checker_path', return_value='/explicit/checker'), \
             patch('eel2_support.server.compiler_check', side_effect=slow_check):
            server = Server(output)
            server.handle(dict(id=1, method='initialize', params={}))
            uri = (self.root/'effect.jsfx').as_uri()
            server.handle(dict(method='textDocument/didOpen', params=dict(textDocument=dict(
                uri=uri, version=1, text='@sample\nx=1;'))))
            self.assertTrue(started.wait(1))
            server.handle(dict(method='textDocument/didChange', params=dict(textDocument=dict(uri=uri, version=2),
                contentChanges=[dict(text='@sample\nx=2;')])) )
            release.set()
            server.executor.shutdown(wait=True)
        self.assertNotIn(b'stale error', output.getvalue())


@unittest.skipUnless(os.environ.get('EEL2_TEST_CHECKER'), 'Optional native checker not built')
class CompilerTests(unittest.TestCase):
    setUp = EditingTests.setUp
    doc = EditingTests.doc
    def test_compiler_rejects_unknown_function_and_maps_line(self):
        doc = self.doc('desc:test\n@sample\nspl0=nonexistent(1);')
        errors = check(os.environ['EEL2_TEST_CHECKER'], self.workspace, doc, [doc])
        self.assertEqual(errors[0]['range']['start']['line'], 2)
        self.assertIn('undefined', errors[0]['message'])

    def test_compiler_does_not_execute_infinite_init_and_checks_gfx(self):
        doc = self.doc('desc:test\n@init\nwhile(1);\n@gfx 100 100\ngfx_line(0,0,1,1);')
        self.assertEqual(check(os.environ['EEL2_TEST_CHECKER'], self.workspace, doc, [doc]), [])

    def test_compiler_uses_unsaved_import_snapshot(self):
        lib = self.doc('@init\nfunction saved(x) (x);', 'lib.jsfx-inc')
        self.workspace.open(lib.uri, '@init\nfunction unsaved(x) (x);', 5)
        doc = self.doc('desc:test\nimport lib.jsfx-inc\n@sample\nspl0=unsaved(1);')
        self.assertEqual(check(os.environ['EEL2_TEST_CHECKER'], self.workspace, doc,
                               [doc] + self.workspace.dependencies(doc)), [])
        self.assertIn('saved(x)', (self.root/'lib.jsfx-inc').read_text())

    def test_compiler_skips_preprocessor_and_missing_imports(self):
        for text in ('@init\n<? while(1); ?>', 'import missing.jsfx-inc\n@sample\nspl0=0;'):
            doc = self.doc(text)
            diagnostics = check(os.environ['EEL2_TEST_CHECKER'], self.workspace, doc, [doc])
            self.assertIn('skipped', diagnostics[0]['message'])
            self.assertEqual(diagnostics[0]['severity'], 3)


if __name__ == '__main__':
    unittest.main()
