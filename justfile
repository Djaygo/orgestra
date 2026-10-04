url := "http://" + env("ORGESTRA_HOST", "127.0.0.1") + ":" + env("ORGESTRA_PORT", "8000")

default:
    @just --list

# Build the three.js stage into src/orgestra/static/dist (`run` serves it when present)
build:
    cd frontend && npm ci && npm run build

# Backend with reload plus the frontend in watch mode, opened in the browser; ctrl-c stops both
dev: build
    #!/usr/bin/env bash
    set -euo pipefail
    trap 'kill $(jobs -p) 2>/dev/null' EXIT
    (cd frontend && npm run dev) &
    (until curl -sf -o /dev/null {{ url }}; do sleep 0.5; done; python3 -m webbrowser {{ url }}) &
    uv run orgestra &
    wait

# Start the app on http://127.0.0.1:8000 (serves the last `just build`)
run:
    uv run orgestra

# Python and frontend checks (run before pushing)
check: check-py check-frontend

check-py:
    uv run pytest
    uv run ruff check
    uv run ruff format --check
    uv run ty check

check-frontend:
    cd frontend && npm run check && npm test && npm run build

# Rebuild data/gotocph from an extraction output dir, e.g. `just dataset ~/extract/gotocph --download`
dataset *args:
    uv run python scripts/build_gotocph_dataset.py {{ args }}

# Record the demo tour; the app must be running (`just run`)
demo out="../demo.mp4":
    cd frontend && npm run demo -- --out {{ out }}
