#!/bin/bash
set -e

echo "=== Plylo – Local Development ==="
export DATABASE_URL="postgresql://localhost/plylo"

# ── Check prerequisites ──────────────────────
command -v psql &>/dev/null || { echo "ERROR: psql not found. Install PostgreSQL first."; exit 1; }
psql -h localhost -d plylo -c "SELECT 1" &>/dev/null || {
    echo "ERROR: Cannot connect to PostgreSQL at localhost/plylo"
    echo "  1. brew services start postgresql@15"
    echo "  2. createdb plylo"
    exit 1
}

# ── Apply forward migrations (non-destructive) ──
echo "Applying migrations..."
PYTHONPATH=. venv/bin/alembic upgrade head 2>&1 || echo "(migrations skipped or already applied)"

# ── Cleanup function ─────────────────────────
PIDS=()
cleanup() {
    echo ""
    echo "Shutting down..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null
}
trap cleanup EXIT INT TERM

# ── Start services ───────────────────────────
echo "Starting API server..."
PYTHONPATH=. venv/bin/uvicorn server.api.main:app --host 127.0.0.1 --port 8000 &
PIDS+=($!)

echo "Starting bot-move worker..."
PYTHONPATH=. venv/bin/python server/jobs/worker.py &
PIDS+=($!)

echo "Starting trainer..."
PYTHONPATH=. venv/bin/python server/jobs/trainer.py &
PIDS+=($!)

echo "Starting Vite dev server..."
cd web && npm run dev &
PIDS+=($!)
cd ..

# ── Wait for API to be ready ─────────────────
echo ""
for i in {1..10}; do
    if curl -sf http://127.0.0.1:8000/api/status >/dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Plylo is running                        ║"
echo "║                                          ║"
echo "║  UI:  http://localhost:5173               ║"
echo "║  API: http://localhost:8000/api/status    ║"
echo "║                                          ║"
echo "║  Press Ctrl+C to stop.                   ║"
echo "╚══════════════════════════════════════════╝"
echo ""

wait
