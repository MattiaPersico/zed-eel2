# EEL2 / JSFX v0.2.0

- Add a JSFX-aware Tree-sitter grammar: metadata and sliders no longer disrupt
  parsing; Zed's outline shows sliders and sections with their nested functions.
- Improve block/argument indentation and add function/section text objects.
- Handle numeric exponents, empty function bodies and namespace parameters in
  the grammar; keep preprocessing opaque and never execute it.
- Expand the JSFX catalog from 63 to 129 functions, including graphics, strings,
  MIDI, memory, file access, routing and sample-accurate automation.
- Show both MIDI signatures and select the four-argument form when appropriate.
- Add grammar corpus/query checks to the release gates alongside the existing
  six-platform/Python combinations and Rust checks.

Python 3.9+ remains required. This is editor support, not compiler or audio
validation. References, rename and automatic formatting remain future work.
Catalog inclusion is pending human submission and maintainer acceptance.
