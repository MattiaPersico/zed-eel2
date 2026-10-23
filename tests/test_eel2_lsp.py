"""Exercise real LSP framing and EEL2 editor behavior without REAPER or Zed."""

import io
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from eel2_support.language import Document, Workspace, TOKEN_TYPES, uri_path
from eel2_support.server import Server, read_message, write_message


class LanguageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="eel2 lsp ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.workspace = Workspace()

    def document(self, text, name="effect.jsfx"):
        return self.workspace.open((self.root / name).as_uri(), text, 1)

    def test_expanded_catalog_completion_hover_and_signature(self):
        cases = [
            ("gfx_blit", "gfx.php", "source", "rotation_y_optional"),
            ("strcpy_substr", "strings.php", "destination", "max_length"),
            ("mem_get_values", "advfunc.php", "buffer", "..."),
            ("midirecv_str", "midi.php", "offset", "string"),
            ("file_riff", "file.php", "handle", "sample_rate"),
            ("slider_next_chg", "vars.php", "slider_index", "next_value"),
        ]
        for name, page, first, last in cases:
            with self.subTest(name=name):
                doc = self.document("@init\n" + name + "(")
                completion = self.workspace.completion(doc, len(doc.text) - 1)
                self.assertIn(name, [item["label"] for item in completion])
                hover = self.workspace.hover(doc, doc.text.index(name))
                self.assertIn("https://www.reaper.fm/sdk/js/" + page, hover["contents"]["value"])
                signature = self.workspace.signature(doc, len(doc.text))
                params = signature["signatures"][0]["parameters"]
                self.assertEqual(params[0]["label"], first)
                self.assertEqual(params[-1]["label"], last)

    def test_midi_overloads_select_four_argument_form(self):
        for name in ("midisend", "midirecv"):
            doc = self.document("@block\n" + name + "(0, 144, 60, ")
            result = self.workspace.signature(doc, len(doc.text))
            self.assertEqual(len(result["signatures"]), 2)
            self.assertEqual(result["activeSignature"], 1)
            self.assertEqual(result["activeParameter"], 3)
            self.assertIn("msg23", self.workspace.hover(doc, doc.text.index(name))["contents"]["value"])
            short = self.document("@block\n" + name + "(0, 144, ")
            self.assertEqual(self.workspace.signature(short, len(short.text))["activeSignature"], 0)

    def test_local_function_overrides_builtin_overloads(self):
        doc = self.document("@init\nfunction midisend(x) (x);\nmidisend(")
        result = self.workspace.signature(doc, len(doc.text))
        self.assertEqual(len(result["signatures"]), 1)
        self.assertEqual(result["signatures"][0]["label"], "midisend(x)")

    def test_optional_variadic_and_zero_argument_signatures(self):
        for source, expected in [("time_precise(", "output_optional"),
                                 ("stack_pop(", "output_optional"),
                                 ("gfx_printf(1,2,3,", "...")]:
            doc = self.document("@init\n" + source)
            result = self.workspace.signature(doc, len(doc.text))
            params = result["signatures"][0]["parameters"]
            self.assertEqual(params[result["activeParameter"]]["label"], expected)
        doc = self.document("@init\nget_host_numchan(")
        result = self.workspace.signature(doc, len(doc.text))
        self.assertEqual(result["signatures"][0]["parameters"], [])
        self.assertNotIn("activeParameter", result)

    def test_headers_are_not_eel2_and_comments_do_not_create_symbols(self):
        doc = self.document('desc:A (strange "title\nslider1:gain=0<0,1>Gain (dB)\n'
                            '@init\n// function fake(x) (x);\n/* @bad [ */\n'
                            'function real(x) local(y) (y = x; y);\n@sample\nspl0 = real(gain);')
        self.assertEqual(doc.issues, [])
        self.assertEqual([s.name for s in doc.symbols if s.kind == 12], ["real"])
        self.assertIn("gain", [s.name for s in doc.symbols])
        self.assertEqual(self.workspace.definition(doc, doc.text.rindex("gain"))[0]["range"]["start"]["line"], 1)

    def test_unicode_paths_and_imports_round_trip(self):
        folder = self.root / "café 🎵"
        folder.mkdir()
        library = folder / "gain.jsfx-inc"
        library.write_text("function scale(x) (x);", encoding="utf-8")
        self.assertEqual(uri_path(library.as_uri()), library)
        doc = self.document('import "café 🎵/gain.jsfx-inc"\n@sample\nspl0=scale(1);')
        self.assertEqual(self.workspace.definition(doc, doc.text.index('scale'))[0]['uri'], library.as_uri())

    def test_local_assignment_does_not_hide_later_global(self):
        doc = self.document('@init\nfunction f(x) local(value) (VALUE=x;);\nvalue=2;\n@sample\nspl0=value;')
        target = self.workspace.definition(doc, doc.text.rindex('value'))[0]
        self.assertEqual(target['range']['start']['line'], 2)

    def test_utf16_positions_and_crlf(self):
        doc = self.document('@init\r\n"🎵"; gain = 1;\r\n')
        offset = doc.text.index("gain")
        self.assertEqual(doc.position(offset), {"line": 1, "character": 6})
        self.assertEqual(doc.offset({"line": 1, "character": 6}), offset)
        self.assertEqual(doc.position(len(doc.text)), {"line": 2, "character": 0})
        self.assertEqual(doc.offset({"line": 1, "character": 999}), doc.text.index("\r", 7))

    def test_strings_character_constants_and_comments_hide_brackets(self):
        doc = self.document("@sample\nx = $'('; y = 'abcd'; z = \"[\\\"(]\"; /* ) */\n// [\nspl0 = sin(0);")
        self.assertEqual(doc.issues, [])

    def test_lexical_diagnostics_and_recovery(self):
        doc = self.document('@init\nx = (1;\n@sample\ny = ];\n@gfx\n"unfinished')
        messages = [d["message"] for d in doc.issues]
        self.assertTrue(any("Unclosed '('" in m for m in messages))
        self.assertTrue(any("Unmatched ']'" in m for m in messages))
        self.assertTrue(any("Unclosed string" in m for m in messages))
        fixed = self.document('@init\nx = (1);\n@sample\ny = 0;\n@gfx\n"finished";')
        self.assertEqual(fixed.issues, [])

    def test_escaped_final_quote_is_not_a_closed_string(self):
        doc = self.document('@init\n"unfinished\\"')
        self.assertTrue(any("Unclosed string" in d["message"] for d in doc.issues))

    def test_sections_in_comments_strings_and_preprocessor(self):
        doc = self.document('/*\n@invalid\n*/\n@init\n"a\n@invalid\nb";\n@sample\nspl0=0;')
        self.assertEqual([t.value for t in doc.sections], ["@init", "@sample"])
        self.assertEqual(doc.issues, [])
        generated = self.document('desc:generated\n<? printf("@sample\\n"); ?>\nx = (\n')
        self.assertTrue(generated.preprocessed)
        self.assertEqual(generated.issues, [])

    def test_case_insensitive_names_and_local_scope(self):
        text = '@init\nvalue=1;\nfunction f(VALUE) local(temp) (temp=VALUE; temp);\n@sample\nspl0=VALUE;'
        doc = self.document(text)
        local = self.workspace.definition(doc, text.index("VALUE;"))[0]
        global_ = self.workspace.definition(doc, text.rindex("VALUE"))[0]
        self.assertEqual(local["range"]["start"]["line"], 2)
        self.assertEqual(global_["range"]["start"]["line"], 1)
        self.assertFalse(any(s.name == "temp" for s in doc.visible(len(text))))
        self.assertIn("sin", [i["label"] for i in self.workspace.completion(self.document('@sample\nSI'), 11)])

    def test_function_visibility_is_section_aware(self):
        text = '@init\nfunction common(x) (x);\n@gfx\nfunction draw(x) (x);\n@sample\ncommon(1); draw(1);'
        doc = self.document(text)
        self.assertTrue(self.workspace.definition(doc, text.rindex("common")))
        self.assertEqual(self.workspace.definition(doc, text.rindex("draw")), [])

    def test_namespace_function_and_namespace_parameter(self):
        text = '@init\nfunction copy(src*, scale) instance(value) (value=src.value*scale);\n@sample\nfilter.copy(other, 2);'
        doc = self.document(text)
        self.assertEqual(doc.issues, [])
        self.assertEqual(self.workspace.definition(doc, text.index("filter.copy"))[0]["range"]["start"]["line"], 1)
        hint = self.workspace.signature(doc, text.index(", 2") + 2)
        self.assertEqual(hint["activeParameter"], 1)
        self.assertEqual(hint["signatures"][0]["parameters"][0]["label"], "src*")
        partial = self.document(text + '\nfilter.co')
        item = self.workspace.completion(partial, len(partial.text))[0]
        self.assertEqual(item["textEdit"]["newText"], "filter.copy")

    def test_nested_calls_and_memory_indexes_count_arguments(self):
        text = '@sample\npow(min(1, 2), buffer[(3; 4)]'
        doc = self.document(text)
        hint = self.workspace.signature(doc, len(text))
        self.assertEqual(hint["signatures"][0]["label"], "pow(x, y)")
        self.assertEqual(hint["activeParameter"], 1)

    def test_completion_mid_identifier_replaces_whole_word(self):
        doc = self.document('@sample\nSINgarbage')
        item = next(i for i in self.workspace.completion(doc, doc.text.index("garbage")) if i["label"] == "sin")
        self.assertEqual(item["textEdit"]["range"], {"start": {"line": 1, "character": 0}, "end": {"line": 1, "character": 10}})

    def test_imports_follow_unsaved_buffers_and_handle_cycles(self):
        a, b = self.root / "a.jsfx-inc", self.root / "b.jsfx-inc"
        a.write_text('import b.jsfx-inc\n@init\nfunction old(x) (x);')
        b.write_text('import a.jsfx-inc\n@init\nfunction helper(x) (x);\n@gfx\nfunction private_draw() (1);')
        doc = self.document('desc:test\nimport a.jsfx-inc\n@sample\nHELPER(1);')
        self.assertEqual(len(self.workspace.dependencies(doc)), 2)
        self.assertEqual(self.workspace.diagnostics(doc), [])
        target = self.workspace.definition(doc, doc.text.index("HELPER"))[0]
        self.assertEqual(target["uri"], b.as_uri())
        self.workspace.open(b.as_uri(), '@init\nfunction changed(x) (x);', 2)
        self.assertEqual(self.workspace.definition(doc, doc.text.index("HELPER")), [])
        items = self.workspace.completion(doc, len(doc.text))
        self.assertIn("changed", [i["label"] for i in items])
        self.assertNotIn("helper", [i["label"] for i in items])
        self.assertNotIn("private_draw", [i["label"] for i in items])
        self.assertEqual(self.workspace.definition(doc, doc.text.index("a.jsfx-inc"))[0]["uri"], a.as_uri())

    def test_import_failures_are_warnings_and_import_budget_is_bounded(self):
        doc = self.document('desc:test\nimport missing.jsfx-inc\n@sample\nspl0=0;')
        diagnostics = self.workspace.diagnostics(doc)
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0]["severity"], 2)
        for i in range(70):
            (self.root / (str(i) + '.jsfx-inc')).write_text('import %d.jsfx-inc\n@init\n' % (i + 1))
        doc = self.document('import 0.jsfx-inc\n@sample\nspl0=0;')
        self.assertEqual(len(self.workspace.dependencies(doc)), self.workspace.MAX_IMPORTS - 1)

    def test_import_lookup_uses_unsaved_symlink_alias(self):
        real = self.root / 'library.jsfx-inc'
        alias = self.root / 'alias.jsfx-inc'
        real.write_text('@init\nfunction saved(x) (x);')
        try:
            alias.symlink_to(real)
        except OSError as error:
            self.skipTest("Symlinks unavailable on this runner: " + str(error))
        self.workspace.open(alias.as_uri(), '@init\nfunction unsaved(x) (x);', 2)
        doc = self.document('import library.jsfx-inc\n@sample\nunsaved(1);')
        target = self.workspace.definition(doc, doc.text.index('unsaved'))[0]
        self.assertEqual(target['uri'], alias.as_uri())

    def test_local_completion_wins_over_import_with_same_name(self):
        (self.root / 'library.jsfx-inc').write_text('@init\nfunction f(imported) (imported);')
        doc = self.document('import library.jsfx-inc\n@init\nfunction f(local_arg) (local_arg);\n@sample\nf')
        item = next(i for i in self.workspace.completion(doc, len(doc.text)) if i['label'] == 'f')
        self.assertEqual(item['detail'], 'f(local_arg)')

    def test_completions_and_hover_ignore_comments_and_strings(self):
        for tail in ('// sin', '"sin"', '/* sin */'):
            doc = self.document('@sample\n' + tail)
            position = doc.text.index('sin') + 1
            self.assertEqual(self.workspace.completion(doc, position), [])
            self.assertIsNone(self.workspace.hover(doc, position))

    def test_semantic_tokens_cover_unicode_and_multiline_comment(self):
        doc = self.document('@sample\n/* 🎵\ncomment */ spl0 = sin(1);')
        values = doc.semantic_tokens()["data"]
        line, col, decoded = 0, 0, []
        for i in range(0, len(values), 5):
            dl, dc, length, kind, _ = values[i:i + 5]
            line, col = line + dl, col + dc if dl == 0 else dc
            decoded.append((line, col, length, TOKEN_TYPES[kind]))
        self.assertIn((1, 0, 5, "comment"), decoded)
        self.assertIn((2, 18, 3, "function"), decoded)
        self.assertEqual(decoded, sorted(decoded))

    def test_plain_eel_and_include_do_not_require_headers(self):
        for name in ("code.eel", "library.jsfx-inc"):
            doc = self.document('function square(x) (x*x);\nvalue=square(2);', name)
            self.assertEqual(doc.issues, [])
            self.assertTrue(self.workspace.definition(doc, doc.text.rindex('square')))

    def reference_spans(self, doc, offset, include=False):
        return [(loc['uri'], loc['range']) for loc in self.workspace.references(doc, offset, include)]

    def assert_references(self, doc, needle, expected, include=False):
        actual = self.reference_spans(doc, doc.text.index(needle), include)
        locations = [(source.uri, source.range(start, start + len(value)))
                     for source, start, value in expected]
        self.assertCountEqual(actual, locations)

    def test_references_separate_parameters_locals_and_globals(self):
        doc = self.document('@init\nx=1;\nfunction a(x) local(tmp) (tmp=x; tmp);\n'
                            'function b(x) static(tmp) (tmp=x; tmp);\n@sample\nx+=1;')
        self.assert_references(doc, 'x=1', [(doc, doc.text.rindex('x'), 'x')])
        self.assert_references(doc, 'x) local', [(doc, doc.text.index('x;'), 'x')])
        self.assert_references(doc, 'tmp) (tmp=x; tmp);\nfunction', [
            (doc, doc.text.index('tmp=x'), 'tmp'), (doc, doc.text.index('tmp);'), 'tmp')])
        self.assert_references(doc, 'x) static', [
            (doc, doc.text.index('x) static'), 'x'), (doc, doc.text.rindex('x;'), 'x')], True)

    def test_references_separate_functions_from_variables_and_sections(self):
        doc = self.document('@init\nf=1; function f(x) (x); f(0);\n'
                            '@gfx\nfunction f(y) (y); f(1);\n@sample\nf(2); value=f;')
        self.assert_references(doc, 'f(x)', [(doc, doc.text.index('f(0)'), 'f'),
                                            (doc, doc.text.index('f(2)'), 'f')])
        self.assert_references(doc, 'f(y)', [(doc, doc.text.index('f(1)'), 'f')])
        self.assert_references(doc, 'f=1', [(doc, doc.text.rindex('f;'), 'f')])
        self.assertEqual(self.workspace.definition(doc, doc.text.index('f(1)'))[0]['range'],
                         doc.range(doc.text.index('f(y)'), doc.text.index('f(y)') + 1))

    def test_references_imported_function_across_open_effects_and_unsaved_include(self):
        library = self.document('function scale(x) (x);', 'library.jsfx-inc')
        first = self.document('import library.jsfx-inc\n@sample\nscale(1);', 'first.jsfx')
        second = self.document('import library.jsfx-inc\n@sample\nscale(2);', 'second.jsfx')
        self.document('@init\nfunction scale(z) (z); scale(3);', 'unrelated.jsfx')
        expected = [(first, first.text.index('scale'), 'scale'),
                    (second, second.text.index('scale'), 'scale')]
        self.assert_references(first, 'scale', expected)
        self.assert_references(library, 'scale', expected)
        self.assert_references(library, 'scale', expected + [(library, 9, 'scale')], True)
        self.workspace.open(library.uri, 'function replaced(x) (x);', 2)
        self.assertEqual(self.workspace.references(first, first.text.index('scale')), [])

    def test_references_globals_share_only_one_effect_import_graph(self):
        library = self.document('function get() global(value) (value);', 'library.jsfx-inc')
        first = self.document('import library.jsfx-inc\n@init\nvalue=1;\n@sample\nvalue;', 'first.jsfx')
        second = self.document('import library.jsfx-inc\n@init\nvalue=2;\n@sample\nvalue;', 'second.jsfx')
        self.document('@init\nvalue=3; value;', 'unrelated.jsfx')
        self.assert_references(first, 'value=1', [
            (first, first.text.rindex('value'), 'value'),
            (library, library.text.index('value'), 'value'),
            (library, library.text.rindex('value'), 'value')])
        locations = self.workspace.references(library, library.text.rindex('value'))
        self.assertEqual({loc['uri'] for loc in locations}, {library.uri, first.uri, second.uri})
        self.assertEqual(len(locations), 4)  # Shared include locations are deduplicated.

    def test_references_namespace_parameters_and_instance_aliases(self):
        doc = self.document('@init\nfunction copy(src*) instance(value) '
                            '(value=src.value; this.value+=src.value; src.other);\n'
                            'function other(src*) (this.value=src.value);\n'
                            '@sample\nobj.value=0; obj.copy(obj);')
        src_uses = [m.start() for m in re.finditer('src\\.', doc.text)]
        self.assert_references(doc, 'src*', [(doc, start, 'src') for start in src_uses[:3]])
        self.assert_references(doc, 'value) (', [
            (doc, doc.text.index('value=src'), 'value'),
            (doc, doc.text.index('this.value') + 5, 'value'),
            (doc, src_uses[0] + 4, 'value'), (doc, src_uses[1] + 4, 'value')])
        self.assert_references(doc, 'value; this', [
            (doc, doc.text.index('src.value') + 4, 'value'),
            (doc, doc.text.index('src.value', doc.text.index('src.value') + 1) + 4, 'value'),
            (doc, doc.text.index('value=src'), 'value'),
            (doc, doc.text.index('this.value') + 5, 'value')])
        self.assertFalse(any(s.name.lower() in ('src.value', 'this.value') and not s.scope for s in doc.symbols))
        self.assertEqual(self.workspace.definition(doc, doc.text.index('this.value') + 5)[0]['range'],
                         doc.range(doc.text.index('value) ('), doc.text.index('value) (') + 5))

    def test_references_namespace_function_calls_and_variable_members(self):
        doc = self.document('@init\nfunction f(x) (x);\n@sample\na.f(1); b.f(2); a.f=3; a.f;')
        self.assert_references(doc, 'f(x)', [(doc, doc.text.index('a.f(1)') + 2, 'f'),
                                            (doc, doc.text.index('b.f(2)') + 2, 'f')])
        self.assert_references(doc, 'a.f=3', [(doc, doc.text.rindex('a.f'), 'a.f')])

    def test_references_slider_headers_utf16_case_and_ignored_text(self):
        doc = self.document('desc:gain gain\r\nslider1:gain=0<0,1>gain\r\n@sample\r\n'
                            '"🎵 gain"; GAIN=1; gain; // gain\r\n/* gain */')
        self.assert_references(doc, 'gain=0', [(doc, doc.text.index('GAIN'), 'GAIN'),
                                              (doc, doc.text.index('gain;'), 'gain')])
        self.assert_references(doc, 'GAIN', [(doc, doc.text.index('gain=0'), 'gain'),
                                           (doc, doc.text.index('GAIN'), 'GAIN'),
                                           (doc, doc.text.index('gain;'), 'gain')], True)
        for needle in ('gain gain', 'gain"', 'gain */'):
            self.assertEqual(self.workspace.references(doc, doc.text.index(needle)), [])

    def test_references_ignore_ambiguous_import_calls_and_preprocessed_source(self):
        library = self.document('function f(x) (x);', 'a.jsfx-inc')
        self.document('function f(y) (y);', 'b.jsfx-inc')
        doc = self.document('import a.jsfx-inc\nimport b.jsfx-inc\n@sample\nf(1);')
        self.assertEqual(self.workspace.references(doc, doc.text.index('f(1)')), [])
        self.assertEqual(self.workspace.references(library, 9), [])
        generated = self.document('@init\n<? printf("x=1;"); ?>\nx=1; x;', 'generated.jsfx')
        self.assertEqual(self.workspace.references(generated, generated.text.rindex('x;')), [])

    def test_scope_recovery_and_no_forward_calls_inside_functions(self):
        doc = self.document('@init\nfunction earlier(x) (x);\n'
                            'function f(x) (earlier(x); later(x); f(x));\n'
                            'function later(x) (x);\n@sample\nf(1);')
        self.assertTrue(self.workspace.definition(doc, doc.text.index('earlier(x);')))
        self.assertEqual(self.workspace.definition(doc, doc.text.index('later(x);')), [])
        self.assertEqual(self.workspace.definition(doc, doc.text.index('f(x));')), [])
        broken = self.document('@init\nfunction f(x) local(temp) (temp=x;\n@sample\nx=1; x;')
        self.assert_references(broken, 'x) local', [(broken, broken.text.index('x;'), 'x')])
        self.assert_references(broken, 'x=1', [(broken, broken.text.rindex('x;'), 'x')])

    def test_references_cycles_and_symlink_aliases_are_deduplicated(self):
        real, alias = self.root / 'real.jsfx-inc', self.root / 'alias.jsfx-inc'
        real.write_text('function old(x) (x);', encoding='utf-8')
        try:
            alias.symlink_to(real)
        except OSError as error:
            self.skipTest('Symlinks unavailable: ' + str(error))
        library = self.workspace.open(alias.as_uri(), 'import effect.jsfx\nfunction f(x) (x);', 2)
        doc = self.document('import real.jsfx-inc\nimport alias.jsfx-inc\n@sample\nf(1);')
        self.assert_references(doc, 'f(1)', [(library, library.text.index('f(x)'), 'f'),
                                            (doc, doc.text.index('f(1)'), 'f')], True)

    def test_references_read_transitive_disk_imports_without_scanning_directories(self):
        (self.root / 'a.jsfx-inc').write_text('import b.jsfx-inc\nfunction caller() (shared());', encoding='utf-8')
        (self.root / 'b.jsfx-inc').write_text('function shared() (1);', encoding='utf-8')
        (self.root / 'unopened.jsfx').write_text('import b.jsfx-inc\n@sample\nshared();', encoding='utf-8')
        doc = self.document('import a.jsfx-inc\n@sample\nshared();')
        a, b = self.workspace.dependencies(doc)
        self.assert_references(doc, 'shared', [(doc, doc.text.index('shared'), 'shared'),
                                              (a, a.text.index('shared'), 'shared'), (b, 9, 'shared')], True)
        self.workspace.MAX_IMPORTS = 2
        self.assertEqual(self.workspace.references(doc, doc.text.index('shared')), [])

    def test_instance_members_do_not_guess_runtime_aliases(self):
        doc = self.document('@init\nfunction f() (this.value=1; this.value; this..value);\n'
                            'function g() (this.value=2; this.value; this..f());\n@sample\na.value=0; a.f();')
        first = doc.text.index('this.value') + 5
        self.assertEqual(len(self.workspace.references(doc, first)), 2)
        self.assertEqual(len(self.workspace.references(doc, doc.text.index('this..value') + 6)), 1)
        self.assertEqual(self.workspace.references(doc, doc.text.index('this..f') + 6), [])

    def test_existing_effects_have_no_lexical_diagnostics(self):
        if not (ROOT / 'effects').is_dir():
            self.skipTest('Private effect collection is not part of the public extension')
        for path in (ROOT / 'effects').rglob('*'):
            if path.suffix in ('.jsfx', '.jsfx-inc'):
                with self.subTest(path=path.name):
                    doc = Document(path.as_uri(), path.read_text())
                    self.assertEqual(self.workspace.diagnostics(doc), [])


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.output = io.BytesIO()
        self.server = Server(self.output)
        self.server.handle(dict(id=1, method='initialize', params={}))
        self.output.seek(0)
        self.initialize = read_message(self.output)
        self.output.seek(0)
        self.output.truncate()
        self.uri = 'file:///tmp/eel2-protocol-test.jsfx'

    def messages(self):
        self.output.seek(0)
        result = []
        while True:
            item = read_message(self.output)
            if item is None:
                break
            result.append(item)
        self.output.seek(0)
        self.output.truncate()
        return result

    def test_initialize_advertises_only_supported_features(self):
        caps = self.initialize['result']['capabilities']
        self.assertEqual(caps['positionEncoding'], 'utf-16')
        self.assertEqual(caps['textDocumentSync']['change'], 1)
        self.assertTrue(caps['renameProvider']['prepareProvider'])
        self.assertTrue(caps['documentFormattingProvider'])
        self.assertTrue(caps['referencesProvider'])
        self.assertEqual(self.messages(), [])

    def test_reference_request_tracks_unsaved_edits_and_include_declaration(self):
        self.server.workspace.open(self.uri, '@init\nx=1; x; // x', 1)
        def request(include):
            self.server.handle(dict(id=2, method='textDocument/references', params=dict(
                textDocument=dict(uri=self.uri), position=dict(line=1, character=0),
                context=dict(includeDeclaration=include))))
            return self.messages()[-1]['result']
        self.assertEqual(len(request(False)), 1)
        self.assertEqual(len(request(True)), 2)
        self.server.handle(dict(method='textDocument/didChange', params=dict(
            textDocument=dict(uri=self.uri, version=2), contentChanges=[dict(text='@init\nx=1; y;')])))
        self.messages()
        self.assertEqual(request(False), [])

    def test_framing_counts_utf8_bytes_and_handles_fragmented_input(self):
        payload = dict(jsonrpc='2.0', id=1, result='🎵 è')
        framed = io.BytesIO()
        write_message(framed, payload)
        class Fragmented(io.BytesIO):
            def read(self, size=-1):
                return super().read(min(size, 3))
        self.assertEqual(read_message(Fragmented(framed.getvalue())), payload)
        with self.assertRaises(ValueError):
            read_message(io.BytesIO(b'Content-Length: 50\r\n\r\n{}'))

    def test_open_change_stale_version_close_clear_diagnostics(self):
        self.server.handle(dict(method='textDocument/didOpen', params=dict(textDocument=dict(
            uri=self.uri, languageId='eel2', version=1, text='@sample\nx=('))))
        self.assertTrue(self.messages()[0]['params']['diagnostics'])
        self.server.handle(dict(method='textDocument/didChange', params=dict(
            textDocument=dict(uri=self.uri, version=2), contentChanges=[dict(text='@sample\nx=(1);')])))
        self.assertEqual(self.messages()[0]['params']['diagnostics'], [])
        self.server.handle(dict(method='textDocument/didChange', params=dict(
            textDocument=dict(uri=self.uri, version=1), contentChanges=[dict(text='@sample\nx=(')])))
        self.assertEqual(self.messages(), [])
        self.server.handle(dict(method='textDocument/didClose', params=dict(textDocument=dict(uri=self.uri))))
        self.assertEqual(self.messages()[0]['params']['diagnostics'], [])
        self.assertNotIn(self.uri, self.server.workspace.documents)

    def test_unchanged_diagnostics_are_not_republished(self):
        for uri in (self.uri, self.uri + '-other'):
            self.server.handle(dict(method='textDocument/didOpen', params=dict(textDocument=dict(
                uri=uri, version=1, text='@sample\nx=1;'))))
        self.messages()
        self.server.handle(dict(method='textDocument/didChange', params=dict(
            textDocument=dict(uri=self.uri, version=2), contentChanges=[dict(text='@sample\nx=2;')])))
        self.assertEqual(self.messages(), [])
        self.server.handle(dict(method='textDocument/didChange', params=dict(
            textDocument=dict(uri=self.uri, version=3), contentChanges=[dict(text='@sample\nx=(')])))
        messages = self.messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['params']['uri'], self.uri)
        self.assertEqual(messages[0]['params']['version'], 3)
        self.assertTrue(messages[0]['params']['diagnostics'])

    def test_unsaved_import_availability_updates_dependents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            effect = (root / 'effect.jsfx').as_uri()
            library = (root / 'library.jsfx-inc').as_uri()
            def open_buffer(uri, text):
                self.server.handle(dict(method='textDocument/didOpen', params=dict(
                    textDocument=dict(uri=uri, version=1, text=text))))
            open_buffer(effect, 'import library.jsfx-inc\n@sample\nspl0=0;')
            self.assertTrue(self.messages()[0]['params']['diagnostics'])
            open_buffer(library, 'function f(x) (x);')
            result = {m['params']['uri']: m['params']['diagnostics'] for m in self.messages()}
            self.assertEqual(result[effect], [])
            self.server.handle(dict(method='textDocument/didClose', params=dict(textDocument=dict(uri=library))))
            result = {m['params']['uri']: m['params']['diagnostics'] for m in self.messages()}
            self.assertTrue(result[effect])

    def test_incremental_edits_use_utf16_and_apply_sequentially(self):
        self.server.workspace.open(self.uri, '@sample\n"🎵"; x=1;', 1)
        self.server.handle(dict(method='textDocument/didChange', params=dict(
            textDocument=dict(uri=self.uri, version=2), contentChanges=[
                dict(range=dict(start=dict(line=1, character=8), end=dict(line=1, character=9)), text='sin(0)'),
                dict(range=dict(start=dict(line=1, character=0), end=dict(line=1, character=6)), text=''),
            ])))
        self.assertEqual(self.server.workspace.documents[self.uri].text, '@sample\nx=sin(0);')

    def test_unknown_request_notifications_and_shutdown(self):
        self.server.handle(dict(id=2, method='unknown'))
        self.assertEqual(self.messages()[0]['error']['code'], -32601)
        self.server.handle(dict(method='$/cancelRequest', params=dict(id=99)))
        self.assertEqual(self.messages(), [])
        self.server.handle(dict(id=3, method='shutdown'))
        self.assertIsNone(self.messages()[0]['result'])
        self.assertEqual(self.server.handle(dict(method='exit')), 0)
        self.assertEqual(Server(io.BytesIO()).handle(dict(method='exit')), 1)

    def test_real_stdio_process_from_unrelated_directory(self):
        stream = io.BytesIO()
        messages = [dict(id=1, method='initialize', params={}),
                    dict(method='initialized', params={}),
                    dict(method='textDocument/didOpen', params=dict(textDocument=dict(
                        uri=self.uri, languageId='eel2', version=1, text='@sample\nspl0=sin(1);'))),
                    dict(id=2, method='textDocument/hover', params=dict(textDocument=dict(uri=self.uri),
                         position=dict(line=1, character=6))),
                    dict(id=3, method='textDocument/semanticTokens/full', params=dict(textDocument=dict(uri=self.uri))),
                    dict(id=4, method='textDocument/references', params=dict(textDocument=dict(uri=self.uri),
                         position=dict(line=1, character=6), context=dict(includeDeclaration=False))),
                    dict(id=5, method='shutdown'), dict(method='exit')]
        for message in messages:
            write_message(stream, dict(jsonrpc='2.0', **message))
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/eel2_lsp.py'), '--stdio'],
                                input=stream.getvalue(), cwd=tempfile.gettempdir(), capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stderr, b'')
        response = io.BytesIO(result.stdout)
        decoded = []
        while True:
            message = read_message(response)
            if message is None:
                break
            decoded.append(message)
        self.assertEqual(len(decoded), 6)
        self.assertIn('sin(x)', decoded[2]['result']['contents']['value'])
        self.assertTrue(decoded[3]['result']['data'])
        self.assertEqual(decoded[4]['result'][0]['range']['start'], dict(line=1, character=5))


if __name__ == '__main__':
    unittest.main()
