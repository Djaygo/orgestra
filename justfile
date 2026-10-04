default:
    @just --list

# Build the three.js stage into src/orgestra/static/dist (`run` serves it when present)
build:
    cd frontend && npm ci && npm run build

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
