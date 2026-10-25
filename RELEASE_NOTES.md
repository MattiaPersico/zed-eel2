# EEL2 / JSFX v0.6.0

- Add incoming and outgoing call hierarchy through Zed's Go menu. Prepare on a
  user function declaration/call or JSFX section header; expand returned callers
  and callees to navigate further.
- Group repeated call sites by function, top-level JSFX section or EEL file.
  Include unopened workspace files, local imports and unsaved buffers, with
  UTF-16 source locations and canonical path deduplication.
- Rebuild analysis from current documents on each expansion. Reject stale items
  with ContentModified instead of navigating to a different symbol after edits.
- Omit built-ins, unresolved/ambiguous calls, dynamic namespace-parameter and this
  calls, and generated or structurally incomplete source. Keep existing workspace
  scan limits and bound graph work, returned items and call-site ranges.

This is static source navigation, not a runtime call graph. Functions not reached
at runtime may still appear. Shared include calls that resolve differently across
effects are omitted. Runtime namespaces and overload/declaration-order semantics
are not fully modeled. No effect code is modified or executed. Python 3.9+ remains
required; catalog submission stays deferred.
