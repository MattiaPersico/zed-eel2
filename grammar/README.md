# EEL2 / JSFX Tree-sitter grammar

Derived from [DyGriin/tree-sitter-eel2](https://github.com/DyGriin/tree-sitter-eel2)
at `97d4ad9b26390fe7c255d36765eda09a2b1ed73c`, retaining its MIT license.
The extension maintains its JSFX additions here so source, fixtures and queries
can be reviewed together. The manifest pins a published commit in this repository.

The external scanner treats metadata, slider definitions, imports and section
headers as line-oriented text. Header descriptions can contain unbalanced quotes,
parentheses and comment-like text without corrupting the code syntax tree.
Sections own their code bodies, allowing Zed's outline to nest functions under
`@init`, `@sample`, `@gfx`, etc. Slider entries retain the complete declaration.
Numeric exponents, empty function bodies, namespace parameters and functions
without a trailing semicolon are also supported.

`<? ... ?>` is opaque preprocessor text. It is never evaluated, so generated
sections/functions cannot appear in the outline. This grammar is an editing aid,
not a substitute for REAPER's compiler. Unknown section labels are retained for
editing; the language server reports unsupported labels separately.

## Regenerate and test

Install `tree-sitter-cli@0.25.10` using npm in an isolated tooling directory.
In this directory run `tree-sitter generate --abi 14` and `tree-sitter test`.
From the repository root run:

```
python3 scripts/check_eel2_grammar.py --cli /absolute/path/to/tree-sitter
```

Commit `src/parser.c`, `src/grammar.json`, `src/node-types.json` and the generated
headers together with source changes. Tests cover metadata, file/list sliders,
quoted imports, section boundaries, comments/strings containing fake headers,
CRLF, preprocessor blocks, core expressions and the Zed queries.
