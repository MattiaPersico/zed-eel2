# EEL2 / JSFX v0.1.1

- Check Python 3.9+ before startup, with fallback between detected interpreters.
- Verify downloaded and cached servers against an embedded SHA-256 digest;
  recover damaged caches and provide actionable download errors.
- Correct file URI conversion on Windows, including paths with Unicode and spaces.
- Remove quadratic assignment indexing, duplicate parsing after edits, and
  unnecessary diagnostic work for unrelated buffers.
- Test Python 3.9 and 3.14 on Linux, macOS and Windows; add a reproducible benchmark.

Python 3.9+ remains required. Diagnostics are structural editor hints, not EEL2
compiler or audio validation. Zed catalog inclusion is pending human submission
and maintainer acceptance.
