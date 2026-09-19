# PROJECT_STATE.md

## Current Progress
- Inspected workspace and read `Plylo-Antigravity-Brief.md`.
- Established `PROJECT_STATE.md` and Antigravity workspace rules (`.agents/rules/invariants.md`).
- **Milestone A completed and verified**.
  - Built headless learner (`server/learning/timeline.py`).
  - Implemented exact-prefix reconstruction via actual update replay (`reconstruct_age`).
  - Executed the 30/20/31 scenario and verified exact prefix isolation.
  - **Repaired Critical Defect:** Fixed replay sampling future-game leakage by correctly slicing `self.games[:new_game.seq - 1]`.
  - **Repaired Moderate Defect:** Forced model into `train()` mode during learning.
- **Milestone B completed**.
  - Built the real persistent backend with PostgreSQL schema via SQLAlchemy.
  - Configured Alembic for migrations.
  - Implemented FastAPI game loop (`server/api/main.py`) with complete routes (create, move, resign, abort, status) and strict turn/termination checks.
  - Implemented leased worker queue for bot moves (`server/jobs/worker.py`).
  - Implemented sequentially consistent background training loop (`server/jobs/trainer.py`).
  - Created integration test script `run_milestone_b.sh` / `test_integration.py`.

## What actually runs
- Python virtual environment is set up with `torch`, `chess`, `fastapi`, `sqlalchemy`, `alembic`, `psycopg2-binary`.
- Engine: `encoder.py`, `model.py`, `search.py`.
- Persistence: `models.py` defines `timelines`, `games`, `moves`, `experience_events`, `training_steps`, `checkpoints`, and `jobs`.
- API: `uvicorn server.api.main:app` handles HTTP requests for game actions.
- Workers: `worker.py` and `trainer.py` continuously process queued jobs.

## Commands and Checks Performed
- `pytest tests/test_milestone_a.py -v`: verified prefix isolation and frozen games.
- `python scratch/review_probe.py`: comprehensive verification of Milestone A invariants.
- `alembic revision --autogenerate`: Generated the persistent database schema migrations.
- **Milestone B Integration Check:** Wrote and ran PostgreSQL-targeted integration tests (`test_integration.py`). PostgreSQL 15 was locally provisioned and the tests passed successfully without using SQLite.

## Any Uncertainty
- Model reproducibility across environments (Mac ARM vs Debian VM) might require strict torch settings.
- The `bot_move` worker instantiates new PyTorch models per move instead of using the fully serialized T+1 snapshots (which depend on blob storage implementation detail from production). The schema includes `file_manifest` for blob storage when migrating to real deployment.

## Remaining Work
- **Milestone C completed**. (Tested, Session Security hardened)
- **Milestone D completed**.
  - Built Explorer exact-prefix backend using sequential `EXISTS` queries against the Postgres `moves` table, strictly bounded by the `sequence <= E` invariant.
  - Implemented Archive and Explorer tabs in React (using conditional rendering layout).
  - Wired PGN export generation supporting standard chess text files.

## Next Steps for Milestone E
1. Review the integrated system as a whole.
2. Formulate deployment topology for the Debian VM.
3. Establish live metrics and telemetry tracking.
