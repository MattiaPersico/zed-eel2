# EEL2 / JSFX v0.4.0

- Add Rename with a prepare step, collision checks and versioned edits. Support
  ordinary user functions, globals, sliders' aliases, parameters, persistent locals
  and namespace parameter prefixes; refuse unsafe/ambiguous or incomplete changes.
- Discover unopened EEL2/JSFX files in explicit workspace folders. Bound scanning,
  skip hidden/build/dependency folders and symlinks, and support additional exclusions.
- Follow statically known namespace calls, namespace arguments and parent-relative
  paths in reference searches. Keep object instances distinct; do not use these
  inferred aliases for automatic rename.
- Add token-preserving formatting: consistent indentation and code trailing-space
  cleanup while preserving headers, comments, strings and line endings. Decline
  incomplete/preprocessed source.
- Add optional ysfx compile-only diagnostics on open/save, with unsaved import
  snapshots, a background worker, stale-result protection and a five-second timeout.
- Publish optional native checkers and license notices for macOS arm64/Intel,
  Linux x86_64 and Windows x86_64, with release checksums.

Python 3.9+ remains required. Compiler checking is optional and needs its native
helper; the other features work with the standard extension. ysfx is not REAPER's
compiler and does not prove audio correctness. No effect code is executed by the
checker. Catalog inclusion still awaits human submission and maintainer acceptance.
