---
name: plylo_invariants
description: Enforces the Plylo maturity invariants for all code changes and architecture decisions.
trigger: always_on
---

# Plylo Maturity Invariants

These invariants MUST be preserved in all code changes. Do not introduce any feature or optimization that violates them.

1. **Exact prefix:** Age n may use knowledge derived from games 1 through n only. It must never use game n+1 or any later game.
2. **No approximation:** Requesting age 4 loads or reconstructs age 4. It must not silently substitute age 0, 5, 100, or a nearby checkpoint.
3. **Frozen game:** Resolve and pin the age, policy version, and model fingerprint at game creation. They never change during that game.
4. **One shared learning stream:** A game played against any old age updates the newest learner when it completes. It does not create a training branch.
5. **One increment:** A qualifying game adds exactly one experience event.
6. **Completion order:** Ordering is acceptance/commit order.
7. **No injected chess expertise:** No pretrained chess weights, opening books, external games, tablebase answers, external engine labels, or LLM move recommendations.
8. **Constant thinking rules:** Age changes learned knowledge, not an artificial depth, skill setting, or blunder probability schedule. The original search settings remain fixed.
9. **No future leakage:** No current opening statistics, globally trained normalization, current transposition entries, latest optimizer state, or unrestricted replay buffer may influence an old brain.
10. **Observable truth:** A completed game is not reported as learned until its update is durably published.
