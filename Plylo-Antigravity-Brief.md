# Plylo build brief for Google Antigravity

Prepared for Claudio on 19 September 2026.

Build a public chess website with one shared opponent that learns from completed visitor games. Visitors can play its newest brain or any exact historical age, measured in games learned. The distinctive feature is a playable history of its learning.

**Working name:** Plylo, pronounced “PLY-low.” A ply is one player's move in chess. **Suggested line:** “Meet Plylo. Teach it chess.” This is a naming proposal; domain availability and trademark clearance are not established.

**Deliverable:** A working, documented, tested web application that Claudio can deploy on his own Debian VM at UpCloud, behind his existing Caddy server. This file is a product brief, engineering specification, implementation sequence, and set of prompts for the coding assistant. It does not claim that the application has already been implemented or benchmarked.

## 1. How to use this brief

Place this file in the project root and attach or reference it in Antigravity. Start with the launch prompt in section 17. Keep the original brief available throughout development; keep a short `PROJECT_STATE.md` recording completed work, remaining work, commands, and design decisions.

Use **Gemini 3.1 Pro as the main builder** given the owner's available quota. Use **Claude Opus 4.6 for a small number of focused reviews**, especially the learning specification before implementation, historical reconstruction after implementation, and concurrency before deployment. This is a practical division of the available budget, not a verified claim that either model is universally better at these tasks. Neither model powers the running chess opponent.

Ask the builder to work through the milestones in order. Complete the small learning experiment before polishing the public site. Each milestone must produce runnable code and concrete evidence, with a checkpoint in `PROJECT_STATE.md`. Do not let a session end with only a plan when the requested milestone can be implemented.

The current Antigravity documentation lists both requested models. It also supports workspace rules. Put a short list of the invariants from section 3 into an always-on workspace rule through the installed version's Customizations interface; keep the full specification as a normal project file. Do not stuff the entire brief into a rules file. [Antigravity models](https://antigravity.google/docs/models), [Antigravity rules](https://antigravity.google/docs/rules-workflows).

## 2. Product intent and first release

Claudio has built several high-performance UCI engines and wants a more engaging experiment: a chess opponent whose experience comes from the people who play it. The objective is to make learning visible and its past playable. There is no requirement to implement UCI or achieve a particular Elo.

A visitor should be able to open the website, choose White or Black, optionally choose an age, and start playing without an account. At the end, the visitor sees how their game entered Plylo's shared history. The default opponent is the latest fully learned age.

The first release includes:

- Standard chess from the normal starting position, with legal moves enforced by the server.
- Play as White, play as Black, flip board, promotion picker, resign, applicable draw claims, move list, and reconnect/resume.
- An exact integer maturity control, including age 0, with an accessible slider and numeric input.
- A stable brain throughout each game, even while other visitors finish games.
- A real learning update for every eligible completed game.
- A game explorer containing only this installation's accepted games, with an explicit age cutoff.
- A game archive and replay, PGN download, and a shareable link to a completed game.
- A short explanation of how learning works and honest completion/learning counters.
- A private operational view for queue health, failed jobs, disk usage, and backups.

Keep accounts, ratings, tournaments, chat, payments, multiplayer, a social feed, clock-based chess, arbitrary starting positions, and variants out of the first release. Do not create a public arbitrary-PGN training upload endpoint.

## 3. Nonnegotiable meaning of maturity

Define one public learning timeline. Its immutable accepted games are `G1, G2, ...`, ordered by their server-side acceptance transactions. A game UUID is its identity; its experience sequence is assigned only when its completed result is accepted.

Let `S0` be the original brain, with rules, material values, and terminal outcomes. Let `U` be the versioned, reproducible learning update. Then:

```text
S0 = original learner state
Sk = U(S(k-1), Gk, permitted replay samples from G1 ... G(k-1))
brain at age n = Sn
```

`Sn` includes learned parameters and all state needed to reproduce further learning. Playing it also requires the associated evaluator, encoder, search configuration, and rule implementation. Historical age is not just a number on a UI or a database filter over current weights.

The following invariants apply everywhere:

1. **Exact prefix:** age n may use knowledge derived from games 1 through n only. It must never use game n+1 or any later game.
2. **No approximation:** requesting age 4 loads or reconstructs age 4. It must not silently substitute age 0, 5, 100, or the nearest saved checkpoint.
3. **Frozen game:** resolve and pin the age, policy version, and model fingerprint at game creation. They never change during that game.
4. **One shared learning stream:** a game played against any old age updates the newest learner when it completes. It does not create a training branch from that old age.
5. **One increment:** a qualifying game adds exactly one experience event, even if the browser retries, refreshes, or reconnects.
6. **Completion order:** ordering is acceptance/commit order, not start time, client time, or a PostgreSQL sequence allocated before completion.
7. **No injected chess expertise:** no pretrained chess weights, opening books, external games, tablebase answers, external engine labels, or LLM move recommendations in the public timeline.
8. **Constant thinking rules:** age changes learned knowledge, not an artificial depth, skill setting, or blunder probability schedule. The original search and exploration settings remain fixed within the timeline.
9. **No future leakage through side channels:** no current opening statistics, globally trained normalization, current transposition entries, latest optimizer state, or unrestricted replay buffer may influence an old brain.
10. **Observable truth:** a completed game is not reported as learned until its update is durably published.

The owner's example is mandatory:

```text
Accepted games = 30; fully learned age = 30.
A visitor starts a game against age 20.
Every bot move in that game uses S20.
The completed game is accepted as G31.
The trainer calculates S31 from S30 and G31, with permitted older replay.
Age 20 remains S20. The new maximum becomes 31 when S31 is published.
```

With simultaneous games, another visitor may take sequence 31 first. The next accepted completion becomes 32. An old-age game never reserves a future experience number at its start.

## 4. What counts as a game learned

Maintain separate values:

| Value | Meaning |
| --- | --- |
| `accepted_game_count` N | Number of validated, eligible completed games durably added to the timeline |
| `trained_through` T | Largest contiguous prefix for which the learner and required public indexes are published |
| `selected_maturity` n | Exact historical age requested for a particular game, with 0 <= n <= T |
| `index_ready_through` E | Internal explorer index watermark; publication must not claim completeness beyond it |

In normal operation N and T stay close. If N is 31 and T is 30, display “31 games completed · learning game 31” and keep the newest playable age at 30. A queued event is not already incorporated knowledge.

For this first release, a qualifying game starts on this server from the standard initial position, contains at least one legal move, and ends in checkmate, a supported rules-based draw, or an explicit player resignation. All such visitor games count equally, including games against age 0. A resignation after moves is a recorded game outcome, not proof that the final position was objectively lost.

An initial-position resignation with no moves is an abort. Browser closure, lost connectivity, a server error, a stale session expiry, or an operational move limit is also an abort unless a legitimate chess result has already occurred. Aborts are not turned into invented wins or draws. Store their operational records separately from the experience stream. Do not raise an arbitrary minimum game length that silently discards real short checkmates.

No clocks in v1. Keep a game resumable for a documented period, initially 24 hours of inactivity. Enforce a high resource ceiling, initially 1,000 plies; reaching it without a chess result aborts the game and supplies no outcome training. These are service limits, not new chess rules.

Before play, explain briefly that completed games become anonymous public training history. Public records use “Visitor,” not identifying account, session, or network information.

## 5. Interface and visual direction

Make this feel like a small chess companion and an interactive experiment. Prioritize a readable board, clear controls, and a sense of history. Avoid a dense engine dashboard.

Suggested visual system: warm off-white background, dark ink text, muted blue and cream squares, a coral accent for the main action, and a small friendly knight or pawn symbol. Use a well-licensed local SVG chess piece set. No generated artwork is required for v1. Avoid copying Lichess branding, proprietary assets, or an entire layout verbatim.

Desktop: board and game controls at the center/left, with age selection and an expandable explorer beside it. Mobile: board first, game controls next, age controls below; move list and explorer in tabs or drawers. Keep touch targets at least 44 CSS pixels and support click-to-move as well as dragging.

### Main play flow

1. Show “Plylo has learned from 8,923 games” using T, with a short “Play its past” explanation.
2. Default to “Latest.” Offer White / Black / Random. If the visitor chooses Black, queue Plylo's first move automatically once the pinned brain is ready.
3. Allow a numeric age and a slider. On Play, atomically resolve Latest to an exact published T and return that number.
4. If reconstruction is cold, show “Preparing Plylo at age 8,923.” Never load a different age behind this message.
5. During play, show “Playing age 8,923” as an unchanging label. Disable changing the current opponent's age; selecting a different age is a new-game action.
6. On completion, show the actual result and “Your game is experience #8,940,” using the sequence assigned at acceptance. Show “Learning…” until that event is included in T.
7. Offer Play again, Replay game, Download PGN, and Explore its games.

### Maturity control

Small histories use a linear integer slider. At larger histories, use a logarithmic slider for reach, plus a numeric input and exact-age buttons for precision. Suggested mapping for a slider fraction t in [0, 1]:

```text
n = round(exp(t * log(T + 1)) - 1)
t = log(n + 1) / log(T + 1), when T > 0
```

A finite slider cannot conveniently select every integer near two million. The numeric input and +/- buttons must be authoritative. Include Latest and Age 0 shortcuts. A historical input stays fixed when new games arrive; Latest follows the newest age only while idle, then freezes when a game starts. Handle T=0 without division by zero.

Shareable age links such as `/?age=8923` must select exactly that age if it exists. Invalid or not-yet-learned values produce an explicit message, not silent clamping. Display “Age: 8,923 games,” not an unsupported “Elo 1,500.”

### Playing details

Show coordinates, last move, legal destinations, check indication, captured pieces, SAN move list, bot-thinking status, and reconnect status. Flipping changes presentation only. Promotion offers queen, rook, bishop, and knight. Keyboard users must be able to select squares and promotion pieces. Respect reduced motion; never communicate side or result through color alone.

Reviewing earlier moves in an active game switches the visible board into review mode. Provide a clear “Return to live game” control. Never submit a move from a historical review position.

The learning panel may report facts such as the number of new positions encountered and whether a game was incorporated. Do not manufacture claims like “I learned the Sicilian” or “I now understand forks.” A changed value estimate is not proof of understanding.

## 6. Recommended learning design

Use a **small value network trained from scratch**, a fixed material prior, and a fixed shallow search. Maintain the full game archive and explorer alongside it. Exact-position memory alone will cover too little of chess; the network gives the experiment a way to generalize across positions.

This remains a research experiment. Sparse visitor games, inconsistent opponents, short resignations, and repeated weak play can produce weak or worse policies. There is no guarantee of monotonic improvement or a particular rating after a given game count. The website must accurately demonstrate learning and measure playing strength separately.

### 6.1 Allowed knowledge at age zero

Use a maintained rules library for legal moves, move application, castling, en passant, promotions, check, checkmate, and supported draws. Material values: pawn 1, knight 3, bishop 3, rook 5, queen 9. The king is handled by terminal rules rather than a capturable material value.

Do not add handcrafted piece-square tables, center-control bonuses, king-safety formulas, pawn-structure evaluation, opening moves, tactical pattern templates, or pretrained features. Shallow lookahead is a general decision procedure over the rules, not learned chess knowledge; disclose it in “How it works.” It remains the same at every age.

Age 0 can take free material and recognize mates visible within its shallow search. It will still make many positional and longer-horizon tactical mistakes. Do not deliberately sabotage it just to make later ages look impressive.

### 6.2 Initial model

Implement a small CPU PyTorch model. Suggested starting architecture:

```text
784 raw features -> Linear(128) -> ReLU -> Linear(32) -> ReLU -> Linear(1)
```

Use a fixed, documented feature ordering:

| Input | Features |
| --- | ---: |
| Twelve piece/color occupancy planes, flattened in fixed square order | 768 |
| Side to move | 1 |
| Four castling-right flags | 4 |
| En-passant file a-h or none, one-hot | 9 |
| Halfmove clock, bounded and scaled by a fixed constant | 1 |
| Current position repetition count, bounded and scaled by a fixed constant | 1 |
| Total | 784 |

Use absolute White/Black board coordinates. Do not infer ownership from screen orientation or from whether the human selected White. Set the en-passant input to none if there is no legally available en-passant capture. Compute repetition information from the saved move history. This compact model input is not a substitute for the full rule state.

Initialize hidden layers using a fixed random seed; initialize the final layer weights and bias to zero. Do not initialize every layer to zero, which would obstruct learning. Thus the learned residual initially contributes exactly zero.

For a nonterminal position s, let:

```text
M(s) = material(White) - material(Black)
f_theta(s) = learned scalar residual
V_theta(s) = tanh(M(s) / 10 + f_theta(s))
```

V is always from **White's perspective**. Positive favors White; negative favors Black. The starting scale 10 is a configurable experimental constant that must be frozen before the public timeline starts. Do not advertise V as a calibrated win probability or centipawn score.

Terminal evaluation bypasses this formula: draws score 0; proven wins/losses score outside the nonterminal range, for example +/-10, with a tiny preference for earlier mate if implemented consistently. Check terminal conditions before a depth cutoff. Material must never outweigh a known checkmate.

### 6.3 Move choice

Use a straightforward fixed two-ply minimax search, with optional alpha-beta pruning once correctness is established. White maximizes the White-perspective score; Black minimizes it. Do not mix White-perspective and side-to-move conventions.

Bound computation with a deterministic node budget, initially 5,000 nodes, and a fixed stable UCI move ordering. Complete the one-ply iteration before starting the two-ply iteration. If the second iteration cannot complete, use the last fully completed iteration. Do not compare some deeply searched moves against others that were cut off early.

A wall-clock watchdog protects the service, but its normal response is to reschedule or report overload, not silently substitute a random move or stronger engine. Record completed depth and nodes so comparisons can account for resource use. Benchmark these starting settings before the public launch and freeze the selected policy configuration.

Resolve ties using a server-generated, persisted game seed. For the initial experiment use a fixed 5% probability of sampling among moves within 0.10 of the best nonterminal score, excluding proven losses when an alternative without a proven loss exists. A proven available mate takes precedence. “Not proven lost” does not mean objectively safe beyond the search horizon. Apply the same policy at age 0 and age two million. Include all constants in the policy version.

Derive move-level randomness from the saved game seed and ply index so crash recovery produces the same action. Provide a deterministic evaluation mode with exploration disabled. Do not use Dropout or model training mode during inference.

Supported draw claims are legal optional actions with value 0. Include them in decision logic, including claims that require declaring an intended legal move. A bot should not be forced to reject a legal draw because it is absent from its action list.

Keep inference independent of the explorer database. In v1, historical move frequencies explain the archive but do not serve as an opening book or tie-breaker. This avoids a second source of policy state and future leakage. Any later empirical-memory policy must be explicitly versioned and restricted to the same exact prefix.

### 6.4 Per-game learning update

Train an outcome value estimator on positions from the completed game and a small replay sample from earlier accepted games. This is an empirical outcome-learning baseline, not AlphaZero, not imitation of every human move, and not a claim of unbiased evaluation under the current policy.

Use a White-perspective target:

```text
White win: z = +1
Draw:      z =  0
Black win: z = -1
Loss: mean((V_theta(s) - z)^2)
```

Positions can come from either player's turns. Include reached positions after moves, including the final nonterminal board when a game ends by resignation. Exclude the initial position and terminal board positions from the main training batch: the initial position is identical in every game, while terminal board outcomes are already implemented by the rules. If a one-move resignation leaves a nonterminal position, it supplies a valid position. A completed legal game must not be dropped solely because it is short.

Initial update settings, subject to the prelaunch learning experiment:

- Sample up to 64 nonterminal positions from the new game using deterministic sampling across its trajectory.
- Sample up to 8 earlier games uniformly by experience sequence, then up to 8 positions per sampled game. At early ages, use the available distinct games.
- When both groups exist, give the current game and replay group equal total loss weight. Normalize within games so long trajectories do not dominate merely by length.
- Run two bounded optimizer steps per accepted game, initially Adam with learning rate 0.001 and gradient norm clipping at 1.0.
- Use a deterministic update seed derived from the timeline seed and k. Record sampled game IDs/plies or a replay manifest sufficient to reconstruct them, plus a digest of the batch.
- Preserve optimizer state. Do not reset Adam for each game or use the newest optimizer when restoring an older state.
- Check finite parameters and losses before publication. A failed update blocks the contiguous training cursor and retries from its previous state; it is not skipped silently.

These settings are hypotheses for a lightweight implementation. Validate them in a separate development experiment before freezing v1. Report failure or weak learning honestly. Adjustments made during development use a disposable development timeline, never secretly rewrite the public one.

There is an important distribution issue: games against old brains and humans are collected under different policies. Their outcomes remain usable training examples, but a loss does not prove every move in that game was bad. This simple outcome learner makes no on-policy reinforcement-learning claim. A later TD, Q-learning, or search-policy learner would require its own specification and new versioned experiment.

The public timeline learns only from actual visitor games. Development fixtures, evaluation games, and any future self-play have separate storage and counters. Background self-play must not inflate “games played with people” or secretly strengthen public age 0.

## 7. Preserving every historical brain

Do not retrain from game 1 for every request. Do not keep only the latest model. Do not store a full permanent model for every single game by default.

Use immutable training events, periodic durable checkpoints, a rolling latest state, and a bounded cache of reconstructed ages:

1. Persist S0, including model, optimizer, seeds, and configuration, before accepting the first public game.
2. Keep periodic full training checkpoints, initially every 100 accepted updates, plus checkpoints for any explicitly retained notable ages.
3. Persist the new latest full state durably after every accepted update; retain only the required rolling/recovery states, periodic checkpoints, and pinned/cached artifacts.
4. Keep a canonical digest for every published step. Hash tensor names, dtypes, shapes, and ordered bytes, plus required optimizer/configuration state. Do not assume a container file's serialization hash alone is a stable logical-state hash.
5. To serve n, load the greatest retained checkpoint c <= n and replay updates c+1 through n in isolation. Each update may sample only games permitted at that update's age, even if the database now contains millions more.
6. Compare the reconstructed digest with the recorded digest at n. Do not serve a mismatching reconstruction as that historical brain.
7. Cache immutable inference-ready snapshots keyed by timeline, policy/runtime version, age, and model digest. Use reference counts or equivalent leases to protect snapshots used by active games.

Example: to serve age 8,923 with a checkpoint at 8,900, reproduce the next 23 updates. Repeated requests reuse the cached result. Coalesce simultaneous reconstruction requests for the same age.

Keep snapshot reconstruction separate from the live trainer. It must never advance T, consume live optimizer state, or publish duplicate training events. Cache eviction removes a derived copy; it never deletes the history required to restore that age.

### Reproducibility is a feature requirement

Pin dependencies, numerical settings, CPU execution configuration, thread counts, encoder, seed derivation, batch order, and training algorithm. Disable nondeterministic operations where supported. Avoid mutable global RNGs shared among jobs. Store the full restore manifest with each checkpoint.

PyTorch does not guarantee identical results across releases, platforms, or CPU/GPU environments. A seed alone is insufficient. Preserve a versioned reconstruction runtime, ideally an archived container image or equivalent reproducible environment, even if application services run natively under systemd. Validate compatibility on a new host before moving the historical service. [PyTorch reproducibility](https://docs.pytorch.org/docs/main/notes/randomness.html).

If a deployment cannot reproduce a published digest, keep serving the verified historical runtime or mark that age temporarily unavailable. Do not call a close numerical approximation the original brain. A requirement for portability across arbitrary future hardware would need a stronger deterministic numerical implementation; document that limit.

Freeze v1's learning and move-selection semantics after launch. Normal UI and operational changes can continue. A changed feature encoder, training algorithm, initialization, material prior, search strength, or exploration schedule creates a clearly named new experiment/timeline; it must not silently redefine old ages. Keep old policy runtimes available for their saved games.

## 8. Server architecture

Use a small monorepo and ordinary services appropriate to one Debian VM.

| Layer | Recommendation | Purpose |
| --- | --- | --- |
| Browser | React, TypeScript, Vite | Responsive chess UI and archive |
| Board UI | Maintained board component or a small accessible board | Display and input; server remains authoritative |
| API | Python, FastAPI, Pydantic | Game sessions, validation, public reads, admin status |
| Rules | `python-chess` | Legal moves, history, outcomes, SAN/PGN |
| Learner | CPU PyTorch | Small value model and sequential updates |
| Database | PostgreSQL | Canonical game history, jobs, indexes, publication pointers |
| Persistence access | SQLAlchemy and Alembic, or an equally explicit migration layer | Transactions and schema changes |
| Background work | PostgreSQL-backed leased jobs and separate worker processes | Bot moves, snapshot restoration, explorer indexing |
| Training | One logically serialized trainer per timeline | Strict ordered learning |
| Hosting | Existing Caddy plus systemd | HTTPS, static frontend, API reverse proxy, service supervision |

Select maintained dependency versions during implementation and commit lockfiles. Do not rely on version ranges or a mutable `latest` tag for the historical runtime. Keep third-party license notices with shipped dependencies and assets. `python-chess` supplies rule facilities; do not use its external engine, opening-book, or tablebase integrations. [Rules library documentation](https://python-chess.readthedocs.io/en/latest/).

Use normal HTTP commands plus polling for game/job state initially. SSE can be added if it simplifies the implementation, but WebSockets are not necessary. Use a bounded CPU process pool for inference and restoration; CPU work must not block the API event loop. Give training and interactive moves separate capacity limits so a reconstruction request cannot starve all active games.

PostgreSQL is sufficient for the initial durable queue. Do not add Redis, Celery, Kubernetes, a vector database, a hosted model API, or a GPU unless measured needs justify them. Store model artifacts outside the web root, with manifests in PostgreSQL; the database is the authority for published state.

Suggested repository structure:

```text
web/                  React application
server/api/           Routes, authorization, request schemas
server/game/          Rules adapter and authoritative game transitions
server/engine/        Encoding, evaluation, search, snapshot inference
server/learning/      Sequential update, replay, checkpoint reconstruction
server/jobs/          Leases, retries, worker entry points
server/storage/       Models, transactions, migrations, artifact manifests
server/explorer/      Historical prefix queries and aggregates
tests/                Rules, learning, timeline, concurrency, browser tests
deploy/               Caddy example, systemd units, environment template
docs/                 Architecture decisions, operating and restore guides
PROJECT_STATE.md      Current progress, commands, next milestone
```

## 9. Data model and publication protocol

Use BIGINT for experience counts and plies where appropriate. Return counts as a documented JSON representation; at the target of two million, JavaScript integers are safe, but avoid an accidental 32-bit database design.

Minimum logical entities:

| Entity | Required content |
| --- | --- |
| `timelines` | ID, immutable initialization/configuration reference, N, T, E, active runtime, status |
| `games` | UUID, timeline, visitor color, pinned age, runtime/model digest, seed, state, result, termination, timestamps, public-share ID |
| `moves` | Game ID, unique ply, UCI, SAN, sufficient history/state checks, prefix key, server-validated actor |
| `experience_events` | Timeline and unique contiguous sequence, unique completed game, trajectory digest, acceptance time |
| `training_steps` | Sequence, parent and output digests, configuration, replay manifest, metrics, publication status |
| `checkpoints` | Exact age, file manifest, logical digest, artifact checksums, runtime reference, retention role |
| `jobs` | Kind, unique deduplication key, status, lease, retry count, payload, failure details |
| `explorer_visits` | Accepted sequence, prefix key, next move, game result, optional move reference |
| `explorer_blocks` | Optional exact aggregates for complete sequence blocks at larger scale |
| `evaluation_runs` | Separate experiment IDs, frozen test configuration, results; never public experience events |

Store full legal move history, not just the latest FEN. Repetition and draw claims can depend on history. FEN is useful for position display and integrity checks, but it cannot reconstruct repetition history by itself.

### Accepting a finished game

In a single database transaction:

1. Lock the game and verify its authoritative final result and eligibility.
2. If an experience event already exists, return that event idempotently.
3. Lock the timeline's acceptance counter row using a consistent lock order across all code paths.
4. Assign k = N+1 and insert one unique experience event for this game.
5. Update N and insert the durable training/index work request, then commit.

Use transactional row-based counter allocation, not a bare sequence whose rollback gaps are treated as missing games. Acceptance order is the order established by this serialized commit path. Keep it short; never train while holding these locks. PostgreSQL documents both row locking and the possibility of gaps in ordinary sequences. [Explicit locking](https://www.postgresql.org/docs/current/explicit-locking.html), [sequence behavior](https://www.postgresql.org/docs/current/functions-sequence.html).

### Publishing the next learned age

Only the trainer holding the timeline lease may process T+1. A database fencing token or equivalent generation check must prevent an expired worker from publishing after another worker takes over.

Load ST and its optimizer; train on G(T+1) plus allowed replay; construct candidate artifacts outside the transaction. Write them to a temporary location, flush, and atomically finalize their immutable artifact paths. Prepare the experience's explorer contributions idempotently.

Then, in a short transaction, verify the fencing token and unchanged parent T, record the training step/manifests, update required index watermarks, and advance the published pointer. Only publish an age whose model and public history cutoff are ready. Readers must never observe new metadata pointing to an incomplete artifact.

If the process dies after files are written but before publication, those files are unreferenced candidates; a retry can reuse a verified candidate or rebuild it. If it dies after commit, a retry detects the already published step and does not train it a second time. Garbage collection must respect published, checkpoint, backup, and active-game references.

Never mutate a model object shared by active inference processes. Training creates a new state; publication swaps a pointer for future requests. Existing games retain their pinned snapshot.

### Reconstructing an old age

Issue a deduplicated restoration job for the requested exact n. The job receives an explicit cutoff and timeline/runtime identifier. All replay queries must enforce each replayed step's permitted maximum. `ORDER BY experience_seq` is mandatory wherever order matters.

The restoration worker verifies its output digest and publishes a cache entry only. If restoring an age is slow, the API returns a pending status and the UI polls. Limit each session's active restoration requests and cache memory use. Never permit a slider drag to enqueue hundreds of jobs; reconstruct only after a deliberate Play or debounced inspection action.

## 10. Game explorer and archive

The explorer uses only accepted games from this installation. Default its cutoff to the selected playable age n. Offer an explicit “All learned games” view, showing its actual cutoff T. Viewing future-to-n archive information must never alter the pinned bot's policy.

Implement an **exact move-prefix explorer** first. The normal starting position is the root. For a sequence such as `e2e4 e7e5 g1f3`, list observed next moves from accepted games with that exact prefix and `experience_seq <= cutoff`.

For each next move display SAN, game count, percentage of the current node's outgoing games, and White win / draw / Black win counts or a clearly labeled bar. Results are from White's perspective, regardless of visitor color or board orientation. Link to a paginated sample of matching games.

Root counts must include only accepted games at the cutoff. If a game ended at the current prefix, it contributes to node visits but has no outgoing next move. Show ended-at-node games separately; do not create a fictitious move or use an inconsistent percentage denominator.

Age 0 has no historical games. An unseen prefix says “Plylo has not played this line at this age.” Never fill empty space with Lichess, master-game, or fabricated data. PGN exports include the bot age and learning-experience number when available, but never session secrets or personal network information.

Use indexed prefix keys plus stored paths or verification data to handle hash collisions safely. An exact-prefix key is distinct from a position key. If a later release merges transpositions, label it “Same position,” include side to move, castling, and legally relevant en-passant state, and define how repeated visits within a game are counted. Do not silently mix prefix and position statistics.

At larger scale, use aggregates for complete blocks of experience sequences plus raw rows for the final partial block. For cutoff n, never include a complete block that extends past n. Current lifetime aggregates cannot answer historical queries by themselves.

## 11. API and game integrity

The API owns legal state, side to move, result, experience sequence, and bot age. The browser submits intentions. It cannot submit a trusted result, overwrite FEN, pick a learned model path, or declare that a game has taught the bot.

Suggested routes:

| Route | Contract |
| --- | --- |
| `GET /api/status` | Timeline ID, N, T, service state, public learning progress |
| `POST /api/games` | Requested color and maturity `latest` or integer; returns game ID, pinned age, preparing/ready status |
| `GET /api/games/{id}` | Authorized active-game state or sanitized public completed-game view |
| `POST /api/games/{id}/moves` | UCI move, expected ply/version, idempotency key |
| `POST /api/games/{id}/resign` | Authenticated game-owner intent and expected state version |
| `POST /api/games/{id}/claim-draw` | Claim type and intended move when required |
| `POST /api/games/{id}/abort` | Owner abort; no experience event |
| `GET /api/explorer` | Explicit timeline, cutoff, prefix, pagination |
| `GET /api/archive` | Public completed games with cutoff and pagination |
| `GET /api/games/{id}/pgn` | Sanitized completed-game PGN |
| `GET /api/health/live` | Process liveness |
| `GET /api/health/ready` | Required dependencies and published brain readiness |

When two browser tabs submit the same move, only one transition occurs. Use a unique `(game_id, ply)` constraint and compare-and-swap or a short row lock around state transitions. Reject stale expected versions with the current authoritative state.

After a valid human move, enqueue a uniquely keyed bot action. A worker computes outside the game lock using the pinned snapshot and expected position. On commit it verifies the game is still active, it is still the bot's turn, and the position version has not changed. Otherwise discard the stale result. A retry must not create two bot moves.

Use an unguessable anonymous session credential in a Secure, HttpOnly, SameSite cookie or equivalent secure ownership mechanism. A public share link grants read-only access, never move authority. Check Origin/CSRF protection on mutating browser endpoints. Rate-limit starts, moves, and snapshot reconstruction; cap each session's active games and enforce a global CPU queue limit. Rate limits reduce automated pollution but cannot guarantee that anonymous visitors play honestly.

Support standard castling, en passant, all promotions, mate, stalemate, and the rules library's supported automatic draws. Implement threefold and fifty-move claims correctly, including an intended move if the claim becomes available only after that move. Do not blindly use `claim_draw=True` to auto-end every claimable position. Use full history for claims and follow checkmate precedence. State supported rule behavior accurately; do not claim a broader arbitrary dead-position solver than the library provides. [python-chess core API](https://python-chess.readthedocs.io/en/latest/core.html).

## 12. Deployment on Debian behind Caddy

The owner controls the VM. Deliver a native systemd deployment as the default. Do not require a managed platform, Firebase, a third-party database, public model inference, or a new reverse proxy.

Use a dedicated unprivileged `plylo` service account. Suggested layout:

```text
/opt/plylo/releases/<release>/     Application and locked Python environment
/opt/plylo/current                Active application release symlink
/var/www/plylo/                   Static frontend build, readable by Caddy
/var/lib/plylo/                   Model artifacts and local durable manifests
/etc/plylo/plylo.env              Secrets and operational configuration
```

Keep PostgreSQL private to the host or its Unix socket. Bind FastAPI to `127.0.0.1:8100`. Run separate API, interactive-worker, and trainer systemd services with restart policies and bounded resource usage. Do not let the API service run training implicitly on every process startup.

Provide real units with the selected virtual-environment paths, `User`, `Group`, `WorkingDirectory`, environment file, restart policy, and appropriate writable paths. Include installation, migration, initialization of S0, startup, health checks, log viewing, and rollback instructions. Preserve the model runtime needed by old ages when changing the application release.

Illustrative Caddy site block, to adapt to the owner's real domain and existing configuration:

```caddyfile
chess.example.com {
    encode zstd gzip

    @api path /api /api/*
    handle @api {
        reverse_proxy 127.0.0.1:8100
    }

    handle {
        root * /var/www/plylo
        try_files {path} /index.html
        file_server
    }
}
```

This preserves the `/api` prefix expected by FastAPI and prevents API errors from becoming SPA HTML. Add suitable index/hashed-asset caching in the implementation. Validate the merged Caddy configuration before a reload, preserve existing sites, and verify direct refreshes of client-side routes. The example is not a substitute for checking the actual server setup. [Caddy SPA and API patterns](https://caddyserver.com/docs/caddyfile/patterns).

Back up PostgreSQL, S0, retained checkpoints, pinned runtime manifests/images, and the model artifacts referenced by the backup's publication watermark. Capture a consistent backup manifest while protecting referenced artifacts from garbage collection. A live database dump plus an unrelated latest-model file is not a reliable restore plan.

Document and perform one restore rehearsal into an isolated environment. Verify N/T, a recent game, and an old reconstructed age. Run database migrations as a separate deployment step. A failed application release should be revertible without renumbering experience or discarding completed games.

Start with the available VM resources; a CPU-only test budget around 4 vCPUs and 8 GB RAM is a reasonable planning assumption, not a capacity guarantee. Measure on the actual host before deciding concurrency. No GPU purchase is required for the proposed small learner.

## 13. Performance and the two-million-game horizon

Design the data model to retain arbitrary historical ages, but distinguish that from proving production capacity for two million games. A visitor waiting for a cold age is acceptable if the UI is honest; silently serving a different age is not.

Initial engineering targets, to be measured and reported on the actual VM:

| Operation | Initial target |
| --- | --- |
| Move validation and API acknowledgement | Under 200 ms at the selected small concurrency |
| Normal bot move | Roughly 0.2-1.5 seconds, with explicit queue feedback under load |
| Warm snapshot load | Under 300 ms |
| Cold age reconstruction | Report measured latency; show preparing state and coalesce requests |
| Learning publication | Normally a few seconds after acceptance at low traffic |
| Prefix explorer | Under 500 ms for common cached/indexed queries |

These are targets, not established benchmarks. Record hardware, dependency versions, concurrent sessions, batch settings, P50/P95 latency, and queue depth. If training is slower than arrivals, display backlog and reduce admission/concurrency or add worker resources; do not silently batch away intermediate ages.

The suggested 784-128-32-1 network has about 105,000 parameters. Float32 weights occupy approximately 0.42 MB; weights plus Adam's main moment tensors occupy roughly 1.26 MB before metadata. At one retained full checkpoint per 100 games, two million games would mean about 20,000 checkpoints, approximately 25 GB for those tensors alone. Checkpoint format overhead, runtime archives, replicas, backups, and game data are additional.

At an illustrative 80 plies per game, two million games produce 160 million plies. Raw moves, explorer rows, and indexes may become the larger storage concern. Measure bytes per game at 10k/100k samples, examine actual query plans, and project capacity before making promises. Do not store a full copy of the explorer or an unbounded permanently retained model for every age.

Adapt checkpoint spacing using measured reconstruction cost and disk budget, without changing the learner. Bound model caches, use batched inference, compact replay manifests, indexed queries, and explicit job admission. PostgreSQL block aggregates, partitions, and an independent artifact disk or object store are later scaling options; the first implementation should not require all of them.

## 14. Validation that protects the idea

Write focused tests for the properties that make this product trustworthy. A screenshot and a working chessboard are insufficient evidence that historical learning works.

### Core acceptance cases

1. **Zero knowledge:** age 0 has no learned residual, no previous games, and no external chess assets. It plays legal moves and values material/mate according to the specification.
2. **Real update:** a controlled valid completed game changes the learner's canonical state when its residual errors are nonzero. The old state remains unchanged. A zero-gradient example may legitimately leave weights unchanged while recording its training step; never claim every game must improve a move.
3. **Prefix isolation:** create two development histories with identical first four games and different later games. Age 4 must reconstruct to the same state and choose the same action for the same history, policy configuration, and seed.
4. **Future data trap:** deliberately populate later experience, current aggregates, caches, and replay entries. Restoring age 4 must neither read nor learn from them.
5. **Exact age:** with only ages 0 and 100 retained as periodic checkpoints, request 4 and 37. Both must reproduce those ages, not one of the checkpoints.
6. **Checkpoint replay:** compare direct chronological training to checkpoint-plus-replay for several intermediate ages. Verify parameters, optimizer state, replay digests, and deterministic decisions within the pinned environment.
7. **Owner's example:** with N=T=30, complete an age-20 game. Confirm it becomes G31, trains S30 into S31, and leaves S20 unchanged.
8. **Concurrency:** simultaneously finish two games at N=30. They receive 31 and 32 exactly once, and training publishes both in order.
9. **Frozen live game:** start at age 20, advance T during play, and verify all subsequent bot moves still use the pinned age/digest.
10. **Retry and crash:** duplicate completion, duplicate move, worker lease expiry, and crashes before/after model publication must not double-count or skip a game.
11. **Perspective:** tests cover White and Black wins, search preference from both sides, draw targets, board flip, and human color. A UI flip cannot reverse a learning label.
12. **Chess correctness:** exercise castling through check, en passant exposing the king, underpromotion, mate versus stalemate, repetition, current and intended-move claims, halfmove counters, and reconnect with full history.
13. **Explorer cutoff:** age 4 shows only accepted games 1-4; pending, aborted, synthetic, and later games are absent. Prefix end-of-game counts and W/D/L totals reconcile.
14. **Ownership and stale state:** a public game URL cannot submit moves; duplicate tabs and stale bot jobs cannot advance the wrong position.
15. **Recovery:** restore a backup and reproduce an old snapshot. Restart services and resume a saved game without losing its pin or adding a second training event.

Use a disposable fixture timeline for controlled trajectories. Fixture injection is a test facility, not a publicly exposed training route. Compare snapshots using fixed seeds and equal search budgets. Browser tests cover the main play flow, selecting Black, age 0, an exact non-checkpoint age, mobile promotion, explorer navigation, and refresh/resume.

### Measuring improvement separately

Run a reproducible evaluation suite at selected ages against the fixed age-0 policy and other frozen snapshots, using both colors and enough games to report uncertainty. Keep evaluation games out of public training and maturity counts. Store the tested runtime, seeds, opening/start conditions, and compute budget.

Report wins, draws, losses, score rate, sample size, and an uncertainty interval that respects any paired-game design. A modest positive result in a tiny sample is not an Elo claim. Do not judge improvement from raw visitor win rates alone because visitor skill and selected ages change.

A working system can learn from data while failing to get stronger. If the experiment shows no measurable improvement, say so and investigate the learner. Do not mask it by increasing search depth with age or substituting a stronger engine.

## 15. Ordered implementation milestones

### Milestone A — Prove learning and history in a headless prototype

Create the repository, locked backend environment, rules adapter, explicit policy manifest, S0, shallow move selection, tiny value network, deterministic per-game update, and checkpoint replay. Use disposable trajectories. Demonstrate age 0, a real update, age 4 after later updates, and the 30/20/31 example. Measure update and reconstruction time.

Deliverable: runnable CLI demonstration plus the core prefix-isolation and replay tests. Establish that the design can learn and reproduce historical state before building the full UI.

### Milestone B — Build the server and persistent game loop

Add PostgreSQL migrations, anonymous session ownership, authoritative moves, accepted-game sequencing, durable jobs, serialized trainer, publication protocol, restart recovery, and frozen game pins. Enforce finite resource limits. Demonstrate multiple simultaneous sessions and a worker crash without double-training.

Deliverable: an API-driven end-to-end game whose completion advances the real shared timeline exactly once.

### Milestone C — Build the playable website

Add the responsive board, color selection, exact-age control, preparing state, promotion, resignation, draw claims, move list, review/live mode, reconnect, and completion/learning messages. All visible counters come from the real backend. Test at desktop and mobile widths.

Deliverable: playable age 0, Latest, and a non-checkpoint historical age with no fake learning data.

### Milestone D — Add the archive and explorer

Implement exact-prefix queries, explicit cutoff filtering, W/D/L counts, empty states, pagination, replay, and PGN export. Add a factual learning explanation and shareable age/game links. Add indexes based on measured query plans.

Deliverable: an explorer that reconciles to the accepted history at several exact cutoffs.

### Milestone E — Review, deploy, and measure

Use the focused Opus review prompt below. Fix substantive findings, complete critical tests, and prepare systemd/Caddy files, backup/restore scripts, and a deployment guide. Run a small concurrency benchmark and document measured capacity. Deploy only when the owner provides the real server access and domain; do not invent them.

Deliverable: deployable v1, an honest validation report, a restore rehearsal, and a short list of known limitations. Production starts with its own empty timeline at age 0; development and test games do not carry over.

## 16. Definition of done

Claudio can deploy the repository on his Debian VM, open the real HTTPS site, choose White or Black, play the newborn or an exact historical Plylo, finish a game, and see it incorporated into the single newest learning stream. The explorer displays only the appropriate recorded history. Refreshes, concurrent players, worker retries, and service restarts preserve the meaning of the selected age.

The repository contains startup and deployment commands, locked dependencies, migrations, a recoverable S0 and checkpoint system, meaningful automated checks, no production seed games, and measured performance notes. It must be possible to explain what the learner actually does without referring to an external chess engine or pretending that a counter is intelligence.

## 17. Prompts for Antigravity

### Launch prompt for Gemini 3.1 Pro

```text
Read Plylo-Antigravity-Brief.md completely and build this project in the current
repository. It is a web chess experiment with a shared learner and exact
historical ages. My production host is my own Debian VM on UpCloud with Caddy.

Treat the maturity invariants as the central product requirement. No pretrained
chess engine, opening book, external game dataset, tablebase, or LLM may supply
the public bot's knowledge. No fake maturity slider, simulated learning counter,
or latest model masquerading as an old age is acceptable.

First inspect the workspace. Write a concise implementation plan, record
important assumptions, and create PROJECT_STATE.md. Put a concise version of
the invariants into the supported Antigravity workspace rules mechanism.

Then implement Milestone A. Do not stop after producing a plan. Build and run
the small headless learner, real per-game updates, exact-prefix reconstruction,
and the 30/20/31 scenario. Use a separate disposable development timeline.

Use the proposed stack and learning baseline unless you find a concrete
correctness or feasibility issue. Explain any material deviation before coding
it. Resolve routine implementation choices yourself. Keep the scope small and
do not substitute an easier product for the exact historical-brain requirement.

At the end, report what actually runs, commands and checks performed, any
uncertainty, and the next milestone. Save that handoff in PROJECT_STATE.md.
```

### Continue prompt for the main builder

```text
Read Plylo-Antigravity-Brief.md and PROJECT_STATE.md, then inspect the current
code before changing it. Complete the next unfinished milestone with runnable
code and the meaningful checks specified in the brief. Preserve the maturity
invariants and separate development/evaluation data from the public timeline.

Do not restart working components or redesign the stack without a concrete
reason. Do not spend the session only planning. Finish the milestone, verify
its acceptance criteria, and update PROJECT_STATE.md with exact next steps.
```

### Focused architecture review for Claude Opus 4.6

```text
Review the Plylo brief and the proposed implementation plan before we commit
to the learning architecture. My Claude quota is limited. Spend your effort
on correctness of exact historical brains and whether the proposed learning
baseline can be implemented coherently on a CPU VM.

Check state completeness, prefix isolation, replay sampling, optimizer/RNG
restoration, the White/Black value convention, terminal handling, mixed-policy
outcome data, fixed search budgets, and exact-age retrieval cost. Distinguish
implementation defects from uncertainty about future playing strength.

Return only material findings, their consequences, and the smallest fixes.
Do not rewrite the whole brief or generate the UI. Do not propose Stockfish
or pretrained data as a substitute for the concept.
```

### Focused implementation review for Claude Opus 4.6

```text
Read the brief, PROJECT_STATE.md, and the specific learning, snapshot,
transaction, and job modules plus their tests. Review the actual code.

Try to falsify these properties:
1. Age n cannot depend on any game greater than n through any model, replay
   query, normalizer, explorer statistic, cache, optimizer, or random state.
2. Playing age 20 when the newest age is 30 updates S30 into S31, never S20.
3. Concurrent completion and worker retry produce one contiguous accepted
   stream and one applied learning update per game.
4. Old games retain the same brain throughout; published files and DB pointers
   remain consistent across crashes and backup restores.
5. A reconstructed non-checkpoint age matches its original state in the pinned
   runtime, including optimizer state and policy configuration.
6. White/Black scoring, claims, promotion, and repetition behave correctly.

Return findings by severity, with concrete file locations, a reproducible
failure scenario or missing test, and a minimal repair. State clearly which
claims you verified and which remain untested. Do not rewrite unrelated code
or spend tokens polishing the UI. If no material finding exists, say so.
```

### Repair prompt for Gemini after review

```text
Address the attached review findings in severity order. Verify each finding
against the actual code, implement the smallest sound repair, and add or update
tests that exercise the underlying failure. Preserve the original product and
historical-age semantics. Report any finding you reject with evidence, then
update PROJECT_STATE.md and resume the next milestone.
```

## 18. Source notes and boundaries

The architecture, formulas, defaults, capacity arithmetic, and implementation milestones above are proposed engineering choices for this project. They are not claims that this exact learner has already achieved a measured chess strength.

- Google documents the available Antigravity reasoning models and their selection behavior: [Models](https://antigravity.google/docs/models). The owner's stated quotas drive the suggested division of work.
- Google's Gemini 3.1 Pro announcement describes the model's reasoning focus: [Gemini 3.1 Pro](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-1-pro/).
- Anthropic describes Opus 4.6's coding and review capabilities: [Claude Opus 4.6](https://www.anthropic.com/research/claude-opus-4-6). Vendor descriptions are not a controlled head-to-head comparison for this project.
- The rules-library source defines available chess operations and limitations: [python-chess](https://python-chess.readthedocs.io/en/latest/) and [core API](https://python-chess.readthedocs.io/en/latest/core.html).
- Numerical reproducibility needs environment controls beyond a seed: [PyTorch reproducibility](https://docs.pytorch.org/docs/main/notes/randomness.html).
- Hosting configuration follows the separation of SPA and API handlers in the official examples: [Caddy common patterns](https://caddyserver.com/docs/caddyfile/patterns).

Recheck installed versions and APIs during implementation. Preserve the public experiment's original runtime and semantics when upgrading its surrounding application.
