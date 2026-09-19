#!/bin/bash
set -e

echo "=== Plylo Milestone B Demo ==="
echo "Checking for PostgreSQL..."

if ! command -v psql &> /dev/null && ! command -v pg_ctl &> /dev/null; then
    echo "[UNVERIFIED] PostgreSQL is not installed or not in PATH."
    echo "Missing prerequisite: PostgreSQL daemon. The maturity invariants require a real database to test concurrency and transactions."
    echo "To run this demo and integration tests, please install and start PostgreSQL:"
    echo "  brew install postgresql@14"
    echo "  brew services start postgresql@14"
    echo "  createdb plylo"
    exit 0
fi

echo "PostgreSQL found. Setting up database..."
export DATABASE_URL="postgresql://localhost/plylo"

# Ensure DB exists (fails silently if already exists)
createdb plylo 2>/dev/null || true

echo "Running Alembic migrations..."
PYTHONPATH=. venv/bin/alembic upgrade head

echo "Starting FastAPI server in background..."
PYTHONPATH=. venv/bin/uvicorn server.api.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!

echo "Starting Worker in background..."
PYTHONPATH=. venv/bin/python server/jobs/worker.py &
WORKER_PID=$!

echo "Starting Trainer in background..."
PYTHONPATH=. venv/bin/python server/jobs/trainer.py &
TRAINER_PID=$!

sleep 2

echo "Running API Demo and Integration Tests..."
PYTHONPATH=. venv/bin/python tests/test_integration.py

echo "Cleaning up..."
kill $API_PID
kill $WORKER_PID
kill $TRAINER_PID
wait $API_PID 2>/dev/null || true
wait $WORKER_PID 2>/dev/null || true
wait $TRAINER_PID 2>/dev/null || true

echo "Done."
