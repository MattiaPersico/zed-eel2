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


## Editing, discovery and compiler checks

### Project symbol search and highlights

Use **project symbols: toggle** (Cmd-T on macOS) to find functions, sliders and assignment-discovered
variables across workspace folders. Matching is case-insensitive: exact names rank
first, then prefixes, substrings and ordered subsequences. Results include file and
section context, exclude function-local variables and preprocessed files, and use
unsaved buffers before disk. Without workspace folders, only open documents and
their imports are searched. At most 256 results are returned; refine the query when
the server logs that results are partial. Discovery uses the bounds/exclusions below;
additional imports of open buffers are limited to 512 indexed documents. Disk files
are checked on each search, so newly created/deleted sources are reflected immediately.

Document highlights match lexical bindings in the current buffer, including slider
aliases and namespace parameter prefixes. They do not scan workspace folders or
infer runtime aliases. The LSP highlight kind is Text; read/write classification is
not claimed. Comments, strings and preprocessed sources are excluded.

The server registers file watchers after initialization only when the client advertises
dynamic registration. Create/change/delete events refresh disk caches, structural
import diagnostics and optional compiler results while retaining unsaved buffers.
There is no polling thread. If registration is unsupported or declined, saving still
refreshes diagnostics and subsequent navigation requests read current disk contents.

Protocol references: [workspace symbols](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#workspace_symbol),
[document highlights](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#textDocument_documentHighlight)
and [file watching](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#workspace_didChangeWatchedFiles).

### Rename

Zed's Rename command supports ordinary user functions, globals, slider aliases,
parameters, local/static variables and namespace parameter prefixes. The server
prepares a range, checks names and completeness, then returns a WorkspaceEdit for
the editor to apply. Open buffers carry their document version; the server never
writes source files. Existing names in the affected scope are conservatively
rejected to avoid capture. Case-only renames are supported.

Rename is deliberately unavailable for built-in/host names, qualified global names,
instance members, functions using instance state, ambiguous/dynamic calls, shared
import globals, formatted-string variable substitutions, preprocessed or incomplete
sources, missing imports and truncated workspace scans. These cases require manual
review; inferred runtime aliases are used for navigation only. Global() constraints,
overloads and imported declaration order are not fully modeled.

### Format

The language server supplies document formatting that normalizes indentation and
removes code trailing whitespace. Zed's tab size and spaces/tabs choice are honored.
It does not split expressions, reorder code or change operators. Header/import/
section lines, multiline strings/comments and line endings are preserved. Incomplete
or preprocessed documents are left unchanged. Formatting tests compare complete
token streams and require idempotence.

### References and workspace discovery

Use **Go > Find All References**. Besides open buffers and local imports, the server
scans the explicit LSP workspace folders on each search. It reads `.jsfx`, `.jsfx-inc`,
`.eel` and `.eel2` files, including unopened importers; unsaved buffers take precedence.
Each scan is bounded to 256 files, 16 MiB, 8192 entries and 16 directory levels.
Hidden entries, symlinks, node_modules, target, dist, build, vendor and __pycache__ are
skipped. Use `lsp.eel2-lsp.initialization_options.exclude` for additional project-relative
glob patterns. This policy does not implement all `.gitignore` rules. A capped or
unreadable scan logs a warning and disables project-wide rename.

Globals stay within each effect's import graph. Shared function declarations retain
their source identity. Static calls such as `a.set()` and `a.get()` connect instance
members to `a.value`; concrete namespace parameters and parent-relative `this..`
paths are followed, up to 128 function/namespace instantiations per graph. Computed
arguments and unresolved calls are not guessed. A shared function may represent
several runtime instances, so these links are possible references, not a proof for
automatic rename. Namespace prefixes and members have distinct selection ranges.

Comments, strings and free-form headers are not reference occurrences. Slider names
and aliases are recognized. First simple assignments are treated as declarations for
includeDeclaration. UTF-16 positions and canonical path deduplication are preserved.
Imports remain relative to each source, at most 64 files per graph and 2 MiB per disk
file; REAPER's global resource search is not reproduced. External disk changes are
picked up through negotiated editor file watchers and on subsequent requests/saves.

### Parsed disk cache

Unchanged disk documents are reused after save and watched-file notifications.
Only notified paths and their cached aliases are invalidated. Open buffers always
win over disk, including unsaved imports. Every read checks file identity, size,
modification time and change time; a read whose stamp changes is retried once,
then declined if still unstable. A metadata cache is not a filesystem snapshot:
filesystems that preserve all these fields require a watcher/save notification.

The LRU cache retains at most 512 files and 16 MiB of source bytes. Parsed objects
consume additional memory, and open buffers are outside this cache budget. Directory
entries are still discovered freshly for project search, references and rename;
new/deleted sources are not hidden behind a cached file list. Symbol search constructs
UTF-16 locations only for its best 256 results, preserving the previous ranking.

### Optional real compilation

The [native checker](../compiler/README.md) links a pinned ysfx EEL2
compiler. It compiles temporary snapshots on open/save and watched-file events, including unsaved imports,
without initializing or running effects. A background worker prevents editor stalls,
results become invalid immediately after edits, and each process has a five-second
timeout. At most eight open JSFX roots are checked per event. Preprocessed/missing/
over-limit imports are explicitly skipped. Diagnostics use source `eel2-ysfx`.

Install the matching checker release and set `EEL2_CHECKER` through Zed's
`lsp.eel2-lsp.binary.env`, or place `eel2-check-v0.5.1` (`.exe` on Windows) alongside
the cached server archive. The rest of the extension does not require this helper.
Its ZIP includes dependency license notices; release checksums are supplied.

ysfx is an independent implementation and may reject newer REAPER-specific APIs.
When imported error locations are ambiguous, the original compiler message appears
at the main file's first line. REAPER compilation and audio testing remain separate
requirements. Built-in diagnostics are still structural checks; a clean result is
not proof of compilation, memory safety or audio behavior. Preprocessing is never
executed, and the API catalog is intentionally incomplete.

The maintained [EEL2 / JSFX grammar](../grammar/README.md) extends the original
MIT-licensed DyGriin grammar. Metadata, slider declarations, imports and section
bodies are recognized directly. Zed's native outline nests functions under their
section. Indentation and function/section text objects use the same syntax tree.
Preprocessor blocks remain opaque; generated code cannot be indexed. Tree-sitter
errors are not published as LSP diagnostics.


## Recorded validation

## Version 0.5.1 project responsiveness

Local validation on 2026-10-25: all 105 workspace tests passed with the native
checker enabled. Seven new regression cases cover atomic replacements, unstable
reads, LRU byte/file limits, unsaved precedence, alias invalidation, save/watch/close
events and fresh references/rename after project changes.

Candidate [workflow 40188943859](https://github.com/MattiaPersico/zed-eel2/actions/runs/40188943859)
passed all six Python combinations, four native compiler builds, grammar and
Rust/WASM checks at `a88b70b9c4b41ce0dafcb7bd489532c8084f5045`.

In Zed on macOS arm64, project search found an unopened imported function. An
external atomic replacement preserving size and mtime was recognized on the next
search. The installed adapter then started the 0.5.1 archive from the normal Zed
cache, without a binary override. An externally introduced compiler error appeared
and cleared after correction without saving or restarting; project search still
worked. Only the temporary test window was closed. No effects were edited and no
REAPER/audio tests were performed.

Release [workflow 40189169730](https://github.com/MattiaPersico/zed-eel2/actions/runs/40189169730)
also passed. All seven published assets matched their GitHub digests, and all four
compiler ZIPs matched `compiler-SHA256SUMS`. The server, adapter and extracted
macOS arm64 checker matched the installed, tested candidate byte for byte.
Catalog submission remains deferred; the catalog fork was not updated.

Server archive SHA-256:
`04a07d7810a88f076f60136f7aebf60c95f93f8dd4ad9cad9fff4c852aed723c`.

A synthetic project with 128 disk files and 12,800 symbols
on the owner's Mac measured broad warm search at 13.29 ms (0.5.0: 30.91 ms), and
search after one notified file change at 16.77 ms (0.5.0: 222.16 ms). Narrow warm
search remained similar: 28.70 ms versus 30.15 ms. These local measurements are
not latency guarantees. Unlike earlier benchmarks, this fixture includes actual
workspace discovery and disk reads. Cold search includes parsing the whole project.

## Version 0.5.0 project navigation

Validation on 2026-10-24:

- All 98 workspace tests passed with the native checker enabled. New coverage
  includes unopened sources, unsaved precedence, fuzzy ordering, result limits,
  file creation/deletion, scope/namespace/slider highlights, watcher negotiation,
  declined registration, and diagnostics after external import changes.
- In Zed 1.25.2 on macOS arm64, Cmd-T found `distant_filter` in an unopened file
  and navigated to its declaration. Selecting a parameter highlighted its three
  occurrences in one function, excluding the other function's same-name parameter.
- Creating a missing include outside Zed cleared both the missing-import warning
  and the compiler-skipped notification, without saving or restarting the server.
- The synthetic 10,000-assignment / 40-import / 21-open-document benchmark measured
  about 76 ms for document highlights and 65 ms for workspace symbols. This fixture
  does not exercise workspace disk scanning; these are not latency guarantees.
- The Windows run found CRLF translation in the test fixture writer. Fixtures now
  write UTF-8 bytes to preserve the requested line endings on every platform.

Candidate [workflow 40105252524](https://github.com/MattiaPersico/zed-eel2/actions/runs/40105252524)
passed all six Python combinations, four native compiler builds, grammar checks and
Rust/WASM checks at source `bc50e9e0f2b77f8e43d2737fe9900f98482a0961`.
The CI archive matched the locally tested server byte for byte. The installed
adapter then started the versioned archive from Zed's normal cache without any
binary override; project search worked, and an external include edit produced and
then cleared a compiler diagnostic. The temporary editor window was closed afterward.

Release [workflow 40105482561](https://github.com/MattiaPersico/zed-eel2/actions/runs/40105482561)
also passed. All seven published assets were downloaded and verified against their
GitHub digests; the four native archives also matched `compiler-SHA256SUMS`.
The published server, WASM adapter and extracted macOS arm64 checker matched the
installed, tested candidate byte for byte.

Server archive SHA-256:
`406dfb7cf091a1f494043a5d92a54b6b395c3e330e0443441e311fc15ee9b1a9`.
No REAPER execution or audio tests were performed, and no effect source was edited.

## Version 0.4.0 editing and compiler integration

Validation on 2026-10-24:

- All 90 workspace checks passed with the native checker enabled. The standalone
  suite passed 68 tests with one expected private-corpus skip.
- [Candidate workflow 40033241890](https://github.com/MattiaPersico/zed-eel2/actions/runs/40033241890)
  passed all six Python 3.9/3.14 combinations, grammar/query checks, Rust tests,
  WASM build and four native compiler builds (Linux x86_64, Windows x86_64,
  macOS arm64 and Intel).
- In Zed 1.25.2 on macOS arm64, Rename changed a shared function declaration and
  two callers, including an unopened file. The editor applied and saved all edits.
  Format indented the function body. An intentional unknown function produced an
  `eel2-ysfx` diagnostic; correcting and saving the source cleared it.
- The installed server automatically discovered the versioned sibling checker and
  returned a real compiler error through LSP without an environment override.
- Formatting all 14 private workspace sources in memory preserved every token and
  was idempotent. No effect files were changed.
- The 10,000-assignment benchmark with 40 imports and 21 open documents measured
  approximately 105 ms parse, 112 ms edit, 7 ms completion and 201 ms references.
  This synthetic benchmark does not measure workspace disk scanning.

Tested source: `62ea5d53568c2f44b0842d8697bf9acae6afa9be`.
Server archive SHA-256:
`7c1f32354fedc43c25efa216b41b85e598309d418db1660e17e9a787f2095204`.
The local server archive was byte-identical to the candidate CI artifact.

The [release workflow 40078220853](https://github.com/MattiaPersico/zed-eel2/actions/runs/40078220853)
also passed. Published server and WASM artifacts are byte-identical to the tested
candidate; all four checker ZIPs match `compiler-SHA256SUMS`, and the macOS arm64
checker executable is byte-identical to the installed/tested candidate. The
[0.4.0 release](https://github.com/MattiaPersico/zed-eel2/releases/tag/v0.4.0)
contains all seven expected assets.

Compiler checks only compile; no REAPER execution, audio or UI testing was performed.


## Version 0.3.0 references and scopes

- Advertise LSP textDocument/references and honor includeDeclaration.
- Resolve calls separately from variables and prefer the current section's functions.
- Keep local variables scoped even when a function body is temporarily incomplete.
- Distinguish namespace parameters and relative instance state from globals.
- Reuse bounded import graphs; preserve unsaved buffers and deduplicate aliases.

Local validation on 2026-10-23: the standalone suite passes 49 tests (one expected private-corpus skip). The reference suite
covers scopes, same-name functions/variables, sections, transitive imports, shared
libraries, unsaved edits, cycles, symlinks, sliders, Unicode/CRLF and protocol frames.
The synthetic 10,000-assignment benchmark with 40 imports and 21 open documents
measured approximately 112 ms parse, 111 ms edit, 8 ms completion and 123 ms references.
These figures are not latency guarantees.

The candidate workflow passed all six Python 3.9/3.14 combinations on Linux,
macOS and Windows, grammar/query validation, two Rust tests and the WASM build:
[run 39979957780](https://github.com/MattiaPersico/zed-eel2/actions/runs/39979957780).
The tested source is `7d35a9fe288aec6f8394f6c906bca4a25e34d01c`; the grammar pin is unchanged.

Manual checks in Zed 1.25.2 on macOS arm64 passed: Find All References on an imported
function displayed its declaration plus three calls in two open effects; references
for a local variable stayed inside its own function despite a same-name parameter
in the effect. Slider reference search selected the header alias and its use.
The installed 0.3.0 adapter then started the checksum-verified cached archive without
a development override, and slider reference search was repeated successfully.
Tests used temporary source files. No effect edits, REAPER compilation or audio
validation were performed. The updated extension retains the same permissions.



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
