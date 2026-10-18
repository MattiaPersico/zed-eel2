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

The pinned [DyGriin EEL2 Tree-sitter grammar](https://github.com/DyGriin/tree-sitter-eel2/tree/97d4ad9b26390fe7c255d36765eda09a2b1ed73c)
parses core EEL2 rather than complete JSFX headers. Its outline, indentation and
bracket features may be incomplete around headers and newer syntax. Full LSP
semantic coloring is enabled to avoid relying on that grammar for JSFX colors.
Zed's outline uses Tree-sitter; LSP document symbols are available to other clients
but do not replace Zed's native outline. Tree-sitter parse errors are not published
as LSP diagnostics.


## Recorded validation

Validation on 2026-10-18 for version 0.1.1: the standalone suite
runs 32 tests with one expected skip for the private effect collection. All six
Python 3.9/3.14 combinations on Linux, macOS and Windows pass, as do the two Rust
unit tests and the `wasm32-wasip2` build. The [release workflow](https://github.com/MattiaPersico/zed-eel2/actions/runs/39118378203)
completed successfully at source commit `c698b4e0a29a1169f6bda7ec7ac25b6543da18d1`.

Manual testing in Zed 1.24.2 on macOS arm64 confirmed EEL2 detection and coloring,
`sin` hover documentation, definition navigation to a local function, a declared
slider and an imported function, and completion plus explicit signature help for
an imported function renamed in an unsaved buffer. An unmatched-parenthesis
diagnostic appeared and cleared after correction. Cached startup passed; after
intentionally corrupting a backed-up server cache, restarting the server downloaded
the released archive, restored the expected SHA-256 digest and launched successfully.
Test files were restored. No REAPER compilation or audio test was performed.
