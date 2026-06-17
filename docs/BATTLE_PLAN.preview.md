# Sentinel — Full Technical Battle Plan
## AINS Hackathon 2026 · Vectors (covectors.io)

> This is the authoritative technical strategy document. Read it before making any architecture, stack, or scope decision.
> For the official judging criteria and use case specs, see `docs/TECHNICAL_SPECS.md`.

---

## 1. The Core Strategy: One System, Not Three Projects

All three use cases share a single OTel GenAI trace spine:

```
[UC3 Atlassian Agent]   ← the real agent we instrument
        ↓  emits gen_ai.* spans
[UC2 Flight Recorder]   ← captures + stores + replays traces
        ↓  feeds traces to
[UC1 Eval Engine]       ← judges traces, produces verdicts
        ↓  files verdicts as
[Jira Issues / Confluence Reports]  ← back into Atlassian
