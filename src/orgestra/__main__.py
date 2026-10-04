"""Run the development server: `uv run orgestra` (or `python -m orgestra`)."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "orgestra.app:create_app",
        factory=True,
        host=os.environ.get("ORGESTRA_HOST", "127.0.0.1"),
        port=int(os.environ.get("ORGESTRA_PORT", "8000")),
        reload=os.environ.get("ORGESTRA_RELOAD", "1") == "1",
    )


if __name__ == "__main__":
    main()
