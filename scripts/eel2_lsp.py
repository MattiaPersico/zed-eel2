#!/usr/bin/env python3
"""Start the EEL2/JSFX language server; no third-party packages required."""

import sys
from eel2_support.server import main

if __name__ == "__main__":
    if "--version" in sys.argv:
        print("eel2-lsp 0.2.0")
    elif "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: python3 eel2_lsp.py [--stdio | --version]\nLSP over standard input/output.")
    else:
        raise SystemExit(main())
