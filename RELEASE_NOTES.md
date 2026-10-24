# EEL2 / JSFX v0.5.0

- Add project-wide symbol search for functions, sliders and assignment-discovered
  globals, including unopened workspace files and unsaved buffers. Rank exact,
  prefix, substring and subsequence matches; return at most 256 results with
  file/section context and precise UTF-16 locations.
- Add document highlights that respect lexical scope, namespace parameter prefixes
  and slider aliases, without scanning workspace folders when the cursor moves.
- Register source-file watchers when the editor supports dynamic registration.
  External file changes refresh import diagnostics and optional compiler results;
  unsaved buffers retain precedence over disk. Clients without watchers still
  refresh on save and read disk changes on subsequent navigation requests.

Project search uses the existing bounded discovery/exclusions and skips preprocessed
sources. Highlights are lexical, not runtime alias or read/write analysis. Python
3.9+ remains required. The optional compile-only helper is distributed for four
platforms; no effect code is executed. Catalog inclusion still awaits human
submission and maintainer acceptance.
