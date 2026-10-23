# EEL2 / JSFX v0.3.0

- Add Find References in Zed for functions, globals, sliders and function variables.
- Search open effects and their bounded local import graphs, using unsaved buffers
  and deduplicating shared includes and symlink aliases. Unopened, unimported files
  are not scanned; unrelated effects keep separate global variables.
- Separate function names from variable names and respect section-local functions.
- Distinguish parameters, persistent locals, namespace parameter prefixes/fields,
  and relative instance members. Link instance(name) to this.name within a function.
- Keep incomplete function bodies scoped while editing and exclude same-file
  recursive/forward function calls from navigation inside function bodies.
- Honor includeDeclaration, case-insensitive names and UTF-16 locations. Ignore
  comments, strings, preprocessed sources and ambiguous imported function calls.

Python 3.9+ remains required. Runtime namespace aliases and cross-function instance
state are not inferred. Rename and automatic formatting remain future work.
This is editor support, not compiler or audio validation. Catalog inclusion is
pending human submission and maintainer acceptance.
