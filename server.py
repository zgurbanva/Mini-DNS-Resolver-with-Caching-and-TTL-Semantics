"""Run the resolver from the repo root: same as ``python -m src.server``.

Implementation lives under ``src/``. Do not run ``python src/server.py`` —
that fails because ``src`` is not on the import path as a package.
"""

from __future__ import annotations

from src.server import main

if __name__ == "__main__":
    main()
