"""Release packaging tests use temporary output and never publish anything."""

import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from package_eel2 import build, version, EXTENSION
from eel2_support.server import read_message, write_message


class ReleaseTests(unittest.TestCase):
    def test_portable_archive_is_reproducible_and_has_only_server_sources(self):
        with tempfile.TemporaryDirectory(prefix="eel2 release ") as directory:
            first, second = [Path(directory) / name for name in ("one.pyz", "two.pyz")]
            self.assertEqual(build(first), build(second))
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(set(archive.namelist()), {
                    "__main__.py", "LICENSE", "eel2_support/__init__.py",
                    "eel2_support/catalog.py", "eel2_support/language.py", "eel2_support/server.py",
                    "eel2_support/project.py", "eel2_support/editing.py", "eel2_support/namespaces.py",
                    "eel2_support/compiler.py", "eel2_support/calls.py",
                })
            with self.assertRaises(FileExistsError):
                build(first)

    def test_packaged_server_matches_adapter_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            digest = build(Path(directory) / "server.pyz")
            self.assertEqual(digest, (EXTENSION / "server.sha256").read_text().strip())

    def test_downloaded_archive_runs_without_workspace_or_site_packages(self):
        with tempfile.TemporaryDirectory(prefix="eel2 café 🎵 ") as directory:
            archive = Path(directory) / ("eel2-lsp-v" + version() + ".pyz")
            build(archive)
            result = subprocess.run([sys.executable, "-S", str(archive), "--version"],
                                    cwd=directory, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "eel2-lsp " + version())
            frames = io.BytesIO()
            for message in [dict(id=1, method="initialize", params={}),
                            dict(id=2, method="shutdown"), dict(method="exit")]:
                write_message(frames, dict(jsonrpc="2.0", **message))
            result = subprocess.run([sys.executable, "-S", str(archive), "--stdio"],
                                    input=frames.getvalue(), cwd=directory, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            output = io.BytesIO(result.stdout)
            initialized = read_message(output)["result"]
            self.assertIn("capabilities", initialized)
            self.assertEqual(initialized["serverInfo"]["version"], version())
            self.assertIsNone(read_message(output)["result"])
            self.assertIsNone(read_message(output))
            self.assertEqual(result.stderr, b"")


if __name__ == "__main__":
    unittest.main()
