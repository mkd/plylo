# VERIFICATION_B.md

## Environment Details
- **Hardware/OS:** macOS ARM (M5 Pro), Darwin 25.6.0
- **Python Version:** 3.14.7
- **PyTorch Version:** 2.14.0
- **PostgreSQL Version:** 15.19 (Running natively on localhost:5432)

## Exact Commands Used for Setup
```bash
# PostgreSQL Local Setup (Development)
HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INTERACTIVE=1 brew install postgresql@15
brew services start postgresql@15
/opt/homebrew/opt/postgresql@15/bin/createdb -h localhost plylo

# Database Migrations
alembic revision --autogenerate -m "Schema updates"
alembic upgrade head
```

## Integration Tests (`tests/test_integration.py`)
- **Passed:** 4/4 integration checks (Anonymous Session, Turn Logic/Moves, Event Assignment, Game Resumption)
- **Failed:** 0
- **Skipped/Unverified:** 0 (PostgreSQL server was successfully provisioned locally)

## Key Assertions Verified
1. **Anonymous Session Ownership:**
   - Attempting a move without a valid token yields HTTP 403.
   - Attempting a move with an incorrect token yields HTTP 403.
   - Using the exact `session_token` from `POST /api/games` yields HTTP 200.
2. **Turn Validation:**
   - Moves are verified via `python-chess` for legality and side-to-move ownership (visitor cannot play Black's move if they are White).
3. **Experience Event Assignment (N+1):**
   - Completing a game via resignation instantly assigns `sequence = 1` inside the API event loop transaction.
   - Atomically increments `Timeline.n_accepted` in PostgreSQL.
4. **Resuming a Game:**
   - Game state, moves, pinned age, and color correctly preserved.
5. **Freeze at Pinned Age:**
   - Created Game 31 asking for age 20. Verified API honors exactly `pinned_age = 20`.
