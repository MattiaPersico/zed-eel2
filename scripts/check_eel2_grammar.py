#!/usr/bin/env python3
"""Validate the grammar corpus and Zed queries with a separately installed CLI."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "tools" / "zed-eel2" if (ROOT / "tools" / "zed-eel2").is_dir() else ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", default="tree-sitter")
    args = parser.parse_args()
    grammar = EXTENSION / "grammar"
    fixtures = sorted((grammar / "test" / "fixtures").glob("*.jsfx"))
    with tempfile.TemporaryDirectory(prefix="eel2 grammar ") as cache:
        env = dict(os.environ, XDG_CACHE_HOME=cache)

        def run(*arguments):
            result = subprocess.run([args.cli, *map(str, arguments)], cwd=grammar,
                                    env=env, capture_output=True, text=True, timeout=90)
            if result.returncode:
                raise SystemExit(result.stdout + result.stderr)
            return result.stdout

        print(run("test"))
        run("parse", "--quiet", *fixtures)
        # CRLF changes line offsets and scanner boundary handling.
        crlf = Path(cache) / "crlf.jsfx"
        crlf.write_bytes(fixtures[0].read_bytes().replace(b"\n", b"\r\n"))
        run("parse", "--quiet", crlf)
        queries = EXTENSION / "languages" / "eel2"
        for query in sorted(queries.glob("*.scm")):
            run("query", "--quiet", query, *fixtures)
        outline = run("query", queries / "outline.scm", fixtures[0])
        names = re.findall(r"capture: \d+ - name, .*text: `(.*)`", outline)
        assert names == [
            "slider1:gain=0.5<0,1,0.01>Gain (dB)",
            "slider2:0<0,2,1{Off,Low,High}>Mode",
            "slider3:/samples:default.wav:Sample file",
            "@init", "scale", "@slider", "@block", "@sample", "@serialize", "@gfx 640 480",
        ], names
        protected = run("query", queries / "outline.scm", fixtures[1])
        assert re.findall(r"capture: \d+ - name, .*text: `(.*)`", protected) == ["@init", "@gfx"]
        # Sections must not indent their entire contents; only actual code blocks do.
        indents = run("query", queries / "indents.scm", fixtures[0])
        assert "@init" not in indents and "@sample" not in indents
        assert "capture:" in indents
        print("Grammar corpus, CRLF, Zed queries and outline boundaries passed.")


if __name__ == "__main__":
    main()
