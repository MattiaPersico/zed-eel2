# EEL2 / JSFX for Zed

Editor support for EEL2 and REAPER JSFX: completion, hover documentation,
signature help, go to definition, local imports, basic diagnostics and coloring.

## Installation

**Catalog status: not yet published to the Zed extension registry.**
A GitHub release is separate from acceptance into Zed's catalog. Once the registry
submission is merged, search Zed Extensions for **EEL2 / JSFX** and choose Install.

Python **3.9 or newer** must be available to Zed as `python3` or `python`.
Rust is not required to use the published extension. On first use the extension
downloads its matching `eel2-lsp-vX.Y.Z.pyz` release from this repository and caches
it in Zed's extension work directory. Subsequent starts use that cached version.
No workspace copy or hardcoded path is needed. Python's version is checked before
startup; if automatic detection finds an incompatible `python3`, it also tries
`python`. An explicitly configured interpreter is never silently replaced.

The adapter checks the server archive against a SHA-256 digest embedded at build
time. A damaged cache is downloaded again and only replaced after verification.
A valid cached server can start offline. If a download fails, restore connectivity
and restart the language server from Zed's command palette.

Open a `.jsfx`, `.jsfx-inc`, `.eel` or `.eel2` file. For semantic coloring in addition to the grammar highlighting, add
this to your existing Zed settings:

```json
{
  "languages": {
    "EEL2": {
      "language_servers": ["eel2-lsp"],
      "semantic_tokens": "full"
    }
  }
}
```

If Python is not on Zed's PATH, configure its absolute executable path under
`lsp.eel2-lsp.binary.path`. To use a development server instead of the release,
set `binary.arguments` to `["/absolute/path/to/scripts/eel2_lsp.py", "--stdio"]`.
The argument list is passed directly and supports paths containing spaces.

## Capabilities and limits

- Completion and reference help for 129 JSFX functions, plus variables, sliders and user functions.
- A JSFX-aware outline containing slider declarations, sections and nested functions.
- Grammar-based block/argument indentation and section/function text objects.
- Hover with official REAPER links; built-in and user-function signature help.
- Definitions in the current document and local imports, including unsaved buffers.
- Case-insensitive lookup and basic function-local/section visibility.
- Structural diagnostics and semantic tokens; LSP document symbols.

This is a lexer and lightweight symbol index, **not an EEL2 compiler**. Diagnostics
cannot establish correct compilation or audio behavior. There is no rename,
formatter, reference search, type checking or complete JSFX/ReaScript API model.
See [limitations and editor smoke test](docs/validation.md).

The maintained [EEL2 / JSFX grammar](grammar/README.md) extends the MIT-licensed
DyGriin grammar. Its source revision is pinned in `extension.toml`. JSFX metadata,
file/list sliders, imports and section bodies are represented directly in the tree.
Preprocessor blocks remain opaque; generated structures cannot be indexed.
REAPER is still needed for final effect compilation and audio testing.

## Development

```sh
python3 -m unittest discover -s tests -v
python3 scripts/package_eel2.py
cargo test --locked
python3 scripts/benchmark_eel2.py
python3 scripts/check_eel2_grammar.py --cli /absolute/path/to/tree-sitter
```

`package_eel2.py` creates a reproducible Python zip application under `dist/` and
refuses overwrites. The archive uses fixed metadata and no compression so its
checksum is identical across platforms and Python versions. After changing server
sources, generate a temporary archive and update `server.sha256` with the printed
digest; tests reject a stale checksum. Launch it with `python3 dist/eel2-lsp-v0.2.0.pyz --stdio`.
No third-party Python modules are needed, and packaging includes only the server.

For development installation in Zed, install a Rust toolchain with the
`wasm32-wasip2` target, then run **zed: install dev extension** and select this
repository root. Zed downloads the WASI SDK for the pinned grammar.
Use the explicit development-server argument override above before a matching
release is available. See [Zed's development guide](https://zed.dev/docs/extensions/developing-extensions).

## Releases and catalog submission

GitHub Actions tests Python 3.9 and 3.14 on Linux, macOS and Windows, validates the
grammar and Zed queries, and builds the WebAssembly adapter on pushes
and pull requests. A `vX.Y.Z` tag additionally creates a GitHub release, after all
checks succeed, containing the portable server and compiled adapter.

Keep the versions in `extension.toml`, `Cargo.toml`/`Cargo.lock`, and the Python
server's version strings aligned before tagging. The adapter downloads the exact
release matching its own version, rather than silently changing server versions.
Do not replace assets of published versions; release a new version instead.

Before requesting catalog inclusion, manually test the exact submitted commit in
Zed. Submit this repository as the `eel2` submodule in
[zed-industries/extensions](https://github.com/zed-industries/extensions), following
[the publishing guide](https://zed.dev/docs/extensions/publishing/publishing-guide).
Catalog acceptance is controlled by Zed's maintainers.

## License

MIT. Copyright 2026 Mattia Persico. The original Tree-sitter grammar is separately
MIT-licensed by DyGriin. Its retained license and the maintained source are under
`grammar/`; modifications are also MIT-licensed.
