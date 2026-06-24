# docs/

Technical documentation for the Sentinel project.

---

## What Goes Here

- Architecture diagram and system overview
- The full technical battle plan (source of truth for design decisions)
- The evaluation report (required hackathon deliverable)
- Any other documentation that is for human readers, not code consumers

## What Does NOT Go Here

- AI agent instructions — those are `CLAUDE.md` and `AGENTS.md` at the root
- Per-package docs — those are each package's `README.md` and `CLAUDE.md`
- Specification proposals — those are in `spec/`

## Documents

| File | Description | Status |
|---|---|---|
| `BATTLE_PLAN.md` | Full technical strategy: architecture, stack decisions, implementation phases | ✅ Complete |
| `ARCHITECTURE.md` | System architecture diagram + component descriptions | ✅ Complete |
| `eval_report.md` | Evaluation results: pass@1=100%, pass^8=33% (CF neuron budget cap during sweep) | ✅ Complete |
| `TECHNICAL_SPECS.md` | Technical Specifications document of the hackathon (source of truth) | ✅ Complete |
| `how_it_works.md` | Narrative walkthrough of the end-to-end loop for non-technical readers | ✅ Complete |
| `validation_guide.md` | 5-minute demo-day walkthrough — Rovo-independent path via backend + dashboard | ✅ Complete |
| `test_report.md` | Full test count and coverage summary across all packages | ✅ Complete |
| `spec_response.md` | Point-by-point response to the hackathon Must/Should specification checklist | ✅ Complete |
| `security_audit.md` | Security hardening audit: constant-time secret compare, run_id validation, batch cap | ✅ Complete |

---



