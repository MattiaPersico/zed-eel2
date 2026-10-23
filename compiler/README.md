# Optional compile-only checker

`eel2-check` links ysfx at commit `8077347ccf4115567aed81400281dca57acbb0cc`.
It loads an isolated JSFX source snapshot and calls `ysfx_compile`, then returns
JSON diagnostics. It never initializes an effect, processes audio, opens its GUI,
runs serialization or executes preprocessing. Graphics functions remain registered
by ysfx's dummy graphics backend so `@gfx` can still be compiled.

This is an independent JSFX implementation, not REAPER's current compiler. Some
newer REAPER APIs and preprocessing are unsupported. Final validation still belongs
in REAPER. Imported compiler errors are reported on the main file at line one,
with the original compiler text, because ysfx does not identify the source of every
compile error. A standalone source error includes a line when the compiler provides it.

## Build

```sh
cmake -S compiler -B .compiler-build -DCMAKE_BUILD_TYPE=Release
cmake --build .compiler-build --config Release --parallel 4
```

The first configure fetches the pinned upstream source and its pinned dr_libs
submodule. The portable EEL backend is used; neither plugins nor graphics windows
are built. On Windows the executable is under `.compiler-build/Release/`.
The small wrapper is MIT; ysfx is Apache-2.0, with additional permissively licensed
components. Release ZIPs include the applicable license notices.

## Enable in Zed

Download the checker ZIP for your platform from the **same extension release**.
Release builds cover macOS arm64/Intel, Linux x86_64 (Ubuntu 22.04 baseline), and
Windows x86_64. Compare its SHA-256 with `compiler-SHA256SUMS` from that release.
Extract it to a permanent folder, retaining `licenses/`, and point Zed at the
absolute executable path using its existing settings:

```json
{
  "lsp": {
    "eel2-lsp": {
      "binary": {
        "env": { "EEL2_CHECKER": "/absolute/path/to/eel2-check" }
      }
    }
  }
}
```

On Windows use `eel2-check.exe` and JSON-escaped backslashes. On macOS/Linux preserve
the executable permission when extracting. Alternatively, put the binary alongside
the server's cached `.pyz` with the name `eel2-check-v0.4.0` (`.exe` on Windows).
The language server recognizes that exact sibling filename automatically. Set
`EEL2_CHECKER` to an empty string to disable compiler checking.

Restart the language server after changing this setting. Compiler checks run in a
background worker on open/save, for up to eight open JSFX roots per event. Edits
immediately clear old compiler results; save again for a fresh check. Unsaved imports
are copied into the snapshot, imports are rewritten to snapshot-local paths, source
files are never modified, and the subprocess is terminated after five seconds.
Missing/over-limit imports and preprocessed sources are explicitly skipped. Without
a configured checker all other language services and structural diagnostics work.

For development tests, set `EEL2_TEST_CHECKER` to the absolute executable path and
run `python3 -m unittest discover -s tests -p test_eel2_editing.py -v`.
