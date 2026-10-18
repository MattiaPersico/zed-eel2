# Validation and limitations

## Editor smoke test


In a temporary JSFX file, paste:

```eel2
desc:LSP smoke test
slider1:gain=0.5<0,1,0.01>Gain

@init
function scale(x amount) (x * amount);

@sample
spl0 = scale(sin(0), gain);
```

- Hover `sin` for reference help and `scale` for its signature.
- Request completion after typing `si`; expect `sin` and `sign`.
- Go to definition on the `scale` call and on `gain`.
- Type `scale(` to request signature help.
- Remove a closing parenthesis and verify a diagnostic; restore it and verify
  that the diagnostic disappears.
- Open a real effect importing `.jsfx-inc` files and navigate to an imported
  function. Edit its name in the open include without saving and check completion.


## Limitations


This is a lexer and lightweight symbol index, **not an EEL2 parser/compiler**.
A clean diagnostics list does not establish valid EEL2 or correct audio behavior.
It does not validate expressions, function arity, memory access, DSP, variable
initialization, recursion restrictions or declaration-order visibility.

Function lookup respects basic section/local scope but is approximate for
namespaces, overloads, global declarations and inherited sections. Namespace
calls fall back to a matching unqualified function; ambiguous matches can return
multiple locations. Globals are indexed from their first simple assignment.
References, rename, formatting and code actions are not implemented.

The curated built-in catalog is intentionally incomplete. Optional parameters
are labelled with `_optional`; variadic entries use `...`. Some alternative
signatures are described in the hover text rather than separate overload entries.

Imports are resolved relative to each importing file, following at most 64 unique
files per lookup and reading at most 2 MiB per disk file. There is no directory
scan and no reproduction of REAPER's resource-directory search. Consequently an
unreadable-local-import warning can refer to a file REAPER would find elsewhere.
Saved imports are checked for changes on the next request/save; external changes
do not proactively notify an idle editor. The server only reads source files.

Files containing `<? ... ?>` preprocessing disable structural diagnostics,
because the generated EEL2 may have a different structure. Completion/navigation
still operate approximately on the source; the preprocessor is never executed.

The maintained [EEL2 / JSFX grammar](../grammar/README.md) extends the original
MIT-licensed DyGriin grammar. Metadata, slider declarations, imports and section
bodies are recognized directly. Zed's native outline nests functions under their
section. Indentation and function/section text objects use the same syntax tree.
Preprocessor blocks remain opaque; generated code cannot be indexed. Tree-sitter
errors are not published as LSP diagnostics.


## Recorded validation

Validation on 2026-10-18 for 0.2.0: the standalone
suite runs 36 tests with one expected skip for the private effect collection.
All six Python 3.9/3.14 combinations on Linux, macOS and Windows pass, as do the
two Rust tests, grammar tests and `wasm32-wasip2` build in
[the candidate workflow](https://github.com/MattiaPersico/zed-eel2/actions/runs/39152882355).
The tested source commit is `dff19ac9ee426ad1f07eebec016470ab133538a0` and the grammar
pin is `1e40912221af48ee7165dbd8f97ab419a36fb4e0`. Seven corpus cases cover JSFX and
plain EEL; additional checks compile every Zed query, assert outline boundaries
and parse CRLF input. The owner's workspace effects/includes also parse without errors.
This is syntax-tree validation, not REAPER compilation.

Manual testing in Zed 1.24.2 on macOS arm64 confirmed grammar-only coloring with
semantic tokens disabled in an isolated project. The symbol picker showed slider
declarations, sections and a function nested under its section. Tests also passed
for `gfx_blit` hover/reference documentation, `gfx_roundrect` completion, automatic
indentation inside a function body, and MIDI signature help selecting the four-
argument form and highlighting `msg3`. Temporary test files were restored.
Text-object queries passed automated checks; Vim-mode motions were not manually tested.

The same startup/download adapter was previously verified in 0.1.1, including
recovery from a deliberately damaged cache. Version 0.2.0's editor smoke test used
a preloaded archive verified against its pinned checksum. The 10,000-assignment
benchmark measured approximately 111/113/14 ms for parse/edit/completion on this Mac;
these are synthetic measurements, not a latency guarantee.
No REAPER compilation or audio test was performed.
