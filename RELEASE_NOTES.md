# EEL2 / JSFX v0.5.1

- Keep unchanged parsed sources on save and watched-file events. Invalidate the
  changed file and cached aliases while preserving unsaved buffers.
- Bound the disk cache to 512 least-recently-used files and 16 MiB of source bytes;
  evict only old entries instead of discarding the entire cache. Parsed Python
  objects use additional memory; open buffers are separate from this budget.
- Detect atomic replacements using file identity and change timestamps as well as
  modification time and size. Retry once when a file changes during a disk read;
  decline unstable snapshots rather than caching mismatched contents.
- Build UTF-16 result locations only for the best 256 symbol matches. Preserve
  ranking, exclusions and fresh directory discovery, including for rename.
- Add regression coverage and a 128-file / 12,800-symbol disk-project benchmark.

Python 3.9+ remains required. No effect source is modified or executed. This is a
performance and robustness update; catalog submission remains deferred.
