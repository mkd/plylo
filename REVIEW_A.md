# REVIEW_A.md — Milestone A Correctness Review

**Reviewer context:** Read the brief sections 3, 6, 7, 14 and Milestone A; read workspace invariants; inspected all source files; ran existing tests (2/2 pass); ran two custom probe scripts with 34 targeted checks. Timings measured on Mac ARM (not the target Debian VM). All findings are against the actual code, not the implementation summary.

---

## Finding 1 — CRITICAL: Replay sampling leaks future games during reconstruction

**Severity:** Critical (violates invariants 1, 9)

**Files:** [timeline.py](file:///Users/claudio/Library/CloudStorage/GoogleDrive-claudiomkd@gmail.com/My%20Drive/projects/plylo/server/learning/timeline.py#L56-L75)

**Problem:** `update_for_game` at line 70 samples replay from `self.games[:-1]`. This list contains *all* games ever appended to the timeline, not just games ≤ `new_game.seq - 1`. When reconstructing age 5 from checkpoint 0 within a timeline that already has 30 games, the replay sample for update 3 (seq=3) can draw games 4–30. This violates "age n may use knowledge derived from games 1 through n only."

**Observed evidence:** Probe explicitly sampled replay for seq=3 in a 10-game timeline. RNG selected game seq 4 as replay — confirmed future leakage. In-place reconstruction of age 4 within a 6-game timeline produced different weights from a clean 4-game timeline (probe FAIL).

**Why existing tests miss this:** `test_prefix_isolation` builds two separate `Timeline` objects and calls `load_checkpoint(4)`, which returns the *saved* dictionary from the checkpoint. It never reconstructs from an earlier checkpoint by replaying updates, so the leaking code path is never exercised.

**Minimal repair:** In `update_for_game`, replace `self.games[:-1]` with `self.games[:new_game.seq - 1]` to enforce the exact-prefix boundary:

```python
# Line 70, current:
past_games = rng.sample(self.games[:-1], num_replay_games)
# Fixed:
past_games = rng.sample(self.games[:new_game.seq - 1], num_replay_games)
```

Add a reconstruction test that builds a 10-game timeline, then reconstructs age 4 from checkpoint 0 using `update_for_game` calls with all 10 games present in `self.games`, and asserts the result matches the original saved age-4 checkpoint.

---

## Finding 2 — MODERATE: Training runs with model in eval mode

**Severity:** Moderate (latent correctness issue, functionally harmless for current architecture)

**Files:** [model.py L67](file:///Users/claudio/Library/CloudStorage/GoogleDrive-claudiomkd@gmail.com/My%20Drive/projects/plylo/server/engine/model.py#L67), [timeline.py L56](file:///Users/claudio/Library/CloudStorage/GoogleDrive-claudiomkd@gmail.com/My%20Drive/projects/plylo/server/learning/timeline.py#L56)

**Problem:** `get_value()` calls `net.eval()` and never restores `net.train()`. If `get_value` is ever called on the trainer's network (or if the network is shared), subsequent training runs with the model in eval mode. The current network has no dropout or batch normalization, so eval vs train mode produces identical forward passes. However, this is a latent bug that would silently corrupt training if the architecture ever adds such layers.

**Observed evidence:** Probe confirmed `net.training == False` both before and after `update_for_game` when `get_value` was previously called on the same net.

**Minimal repair:** Add `self.net.train()` at the top of `update_for_game`. Optionally, have `get_value` save/restore mode or accept mode as a parameter.

---

## Finding 3 — MODERATE: No reconstruction code path exists; test does not test reconstruction

**Severity:** Moderate (claimed capability is absent, not merely untested)

**Files:** [timeline.py L40-45](file:///Users/claudio/Library/CloudStorage/GoogleDrive-claudiomkd@gmail.com/My%20Drive/projects/plylo/server/learning/timeline.py#L40-L45), [test_milestone_a.py L102-127](file:///Users/claudio/Library/CloudStorage/GoogleDrive-claudiomkd@gmail.com/My%20Drive/projects/plylo/tests/test_milestone_a.py#L102-L127)

**Problem:** Milestone A saves every single age as a checkpoint (line 53: `self.save_checkpoint(seq)` inside `add_game_and_train`). There is no `reconstruct_age(n, from_checkpoint)` function. The `load_checkpoint` method is a dictionary lookup. The brief requires (section 7): "to serve n, load the greatest retained checkpoint c ≤ n and replay updates c+1 through n in isolation." This code path does not exist.

The demo's "Exact-Prefix Reconstruction (Age 4)" at `run_milestone_a.py` line 81 just does a dictionary lookup — it is a `load_checkpoint`, not a reconstruction. `PROJECT_STATE.md` claims "Implemented exact-prefix reconstruction via `load_checkpoint(age)`" which conflates checkpoint retrieval with reconstruction.

**Why it matters:** Without reconstruction, saving every checkpoint is the only way to serve any age. The brief's architecture for production (periodic checkpoints + replay) is untested. Even if Finding 1 is fixed, there is no evidence that replaying from a prior checkpoint produces the correct state, because that code path has never been written or run.

**Minimal repair:** Write a `reconstruct_age(target_age)` function that finds the highest checkpoint ≤ target, loads it, and replays updates through `target_age`. After fixing Finding 1, add a test that:
1. Builds a 20-game timeline saving checkpoints only at ages 0 and 10.
2. Reconstructs ages 4 and 15.
3. Compares against the states from a reference timeline that saved every age.
4. Verifies both net parameters and optimizer moments/step counters match.

---

## Finding 4 — LOW: No model/state digest computation

**Severity:** Low (section 7 requirement, not blocking A correctness but needed before B)

**Files:** All — no digest code exists.

**Problem:** The brief section 7.4 requires: "Keep a canonical digest for every published step." No digest (hash of tensor state) is computed or compared anywhere. Without digests, reconstructed states cannot be verified against originals at runtime, and the "compare the reconstructed digest with the recorded digest" safety net does not exist.

**Minimal repair (for B):** Implement a deterministic digest function over ordered tensor bytes plus optimizer state. Record at each save; verify at each load/reconstruct.

---

## Finding 5 — LOW: No pinned dependencies or lockfile

**Severity:** Low (section 8 requirement, practical risk for reproducibility)

**Problem:** There is no `requirements.txt`, `pyproject.toml`, or lockfile. Dependencies were installed via bare `pip install torch chess pytest` without version pins. The brief states: "Select maintained dependency versions during implementation and commit lockfiles." PyTorch reproducibility across versions is not guaranteed (section 7 / PyTorch docs).

**Minimal repair:** Run `pip freeze > requirements.txt` and commit it. Use exact versions (`torch==2.14.0`, etc.).

---

## Finding 6 — LOW: Dead code and minor issues in model.py

**Severity:** Low (cosmetic, no correctness impact)

**Files:** [model.py L11-12](file:///Users/claudio/Library/CloudStorage/GoogleDrive-claudiomkd@gmail.com/My%20Drive/projects/plylo/server/engine/model.py#L11-L12)

**Problem:** `gen = torch.Generator(); gen.manual_seed(seed)` at lines 11–12 creates a generator that is never used. The actual seeding is done via `torch.manual_seed(seed)` inside `fork_rng`. This is confusing but harmless.

**Repair:** Remove the unused `gen` variable.

---

## Finding 7 — LOW: Ply-2 fallback edge case

**Severity:** Low (information loss in rare edge case, no incorrect results)

**Files:** [search.py L107-108](file:///Users/claudio/Library/CloudStorage/GoogleDrive-claudiomkd@gmail.com/My%20Drive/projects/plylo/server/engine/search.py#L107-L108)

**Problem:** If ply-2 evaluation completes all moves but `nodes` equals `max_nodes` exactly, the code falls back to ply-1 results despite ply-2 being complete. The check `if nodes >= max_nodes` should exclude the case where `len(scored_moves_2) == len(legal_moves)`.

**Repair:** Change the fallback condition to: `if nodes >= max_nodes and len(scored_moves_2) < len(legal_moves)`.

---

## Checks verified as correct

| Property | Observed evidence |
|---|---|
| Age-0 learned residual is zero | fc3 weight and bias are all zeros; fc1/fc2 have non-zero Kaiming init |
| Training produces genuine weight changes | fc3 weights change after game 1; S0 checkpoint unaffected |
| White/Black terminal signs | Checkmate when Black is mated: +10; when White is mated: −10 |
| Material baseline sign | Starting position: M=0. White material advantage → positive M |
| V formula: `tanh(M/10 + f_θ)` | Correctly bounded to (−1, +1) for non-terminal; terminals bypass at ±10 |
| S0 checkpoint immutability | `copy.deepcopy` protects checkpoints from mutation by training |
| 30/20/31 genuinely trains S30→S31 | Optimizer step advances 60→62; weights change; S20 and S30 checkpoints unchanged |
| Model init is deterministic | Two `PlyloNet(seed=42)` instances produce identical weights |
| Search handles both colors | White maximizes, Black minimizes; tested from starting position and after 1.e4 |
| Terminal detection | Checkmate, stalemate, game-over correctly detected and scored |
| Node budget enforcement | Tiny budget returns partial ply-1; moderate budget falls back from incomplete ply-2 |
| Workspace rules file | `.agents/rules/invariants.md` exists with correct YAML frontmatter (`trigger: always_on`) |

---

## Checks NOT run

| Check | Reason |
|---|---|
| Disk-serialized reconstruction from a fresh process | No disk serialization exists. This is Milestone B work, not an A defect. |
| Cross-platform or cross-PyTorch-version reproducibility | Requires running on the target Debian VM. Not testable locally. |
| Draw claim logic (threefold, fifty-move with intended move) | No test was written for this specific path. The brief's section 14.12 requires it. |
| Castling through check, en passant exposing king | Depends on python-chess correctness; not independently tested. |
| Concurrency (two simultaneous game completions) | In-memory single-threaded design; meaningful concurrency testing is B work. |
| Explorer cutoff accuracy | Explorer not implemented (Milestone D). |
| Chess strength measurement | Explicitly out of scope for this review; passing tests say nothing about playing strength. |

---

## Timing observations

| Operation | Measured (Mac ARM, in-process) |
|---|---|
| S0 initialization | 1.3 ms |
| Training 30 games sequentially | 2,088 ms total (69.6 ms/game) |
| Reconstruct age 15 from S0 (15 replays) | 912 ms (60.8 ms/step) |
| Single game training step | ~70 ms |

These timings are measured on the development Mac, not the target Debian VM. The per-step reconstruction cost (~61 ms) means reconstructing age 2,000,000 from checkpoint 0 would take ~34 hours. Periodic checkpoints at the planned 100-game interval would cap reconstruction at ~6 seconds worst case, which is acceptable.

---

## Verdict

The foundation is **ready for Milestone B after repairing Finding 1** (replay leakage). This is a one-line fix but it is critical — without it, reconstruction from a prior checkpoint produces wrong historical states, violating the central product requirement.

Finding 2 (train/eval mode) should be fixed concurrently as it is trivial. Finding 3 (no reconstruction code path) should be addressed as part of the Finding 1 fix — write the reconstruction function and a test that exercises it.

Findings 4–7 are low severity and can be addressed during Milestone B setup.

The existing tests pass but are insufficient: they test checkpoint *retrieval*, not *reconstruction*. After fixing Finding 1, the new reconstruction test is the most important addition before moving to B.
