# tests/

Cross-package end-to-end integration tests.

---

## What Goes Here

- E2E tests that span multiple packages and require all services to be running
- Tests that verify the full loop: agent run → trace captured → verdict produced → Jira issue filed

## What Does NOT Go Here

- Unit tests — those live in each package's own `tests/` directory
- Integration tests that only involve one package — those also live inside that package

## The Distinction

| Location | Type | Requires services? |
|---|---|---|
| `packages/*/tests/unit/` | Unit — mocked dependencies | No |
| `packages/*/tests/integration/` | Integration — one package + real external service | Optional |
| `tests/e2e/` | End-to-end — all packages + all services | Yes |

## Running E2E Tests

```bash
# E2E tests require all services running
make dev          # in one terminal

# Then in another terminal
make test-e2e
```

## E2E Test Scenarios

| Test | What It Covers |
|---|---|
| `test_full_happy_path.py` | Synthetic incident → agent run → flight recorder captures → eval verdict → Jira issue filed |
| `test_failure_attribution.py` | Deliberate retrieval failure → verdict attributes to correct step → replay bisects to that step |
| `test_deterministic_replay.py` | Record a run → replay it → assert zero live API calls were made |
| `test_drift_detection.py` | Two runs with different output distributions → drift alert fires |
