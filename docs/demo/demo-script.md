# Sentinel — Demo Video Script (≤ 5:00)

> One incident, end to end, through all three use cases. Word-for-word narration +
> exact on-screen actions. Triggers the loop by **API** (no dependency on the Rovo
> chat surface, which is pending Rovo enablement on the instance).
>
> **Legend:** ▶ = do this on screen · 🎙 = say this (verbatim) · 💡 = note to self

---

## 0. Before you hit record (5 minutes of prep)

> ⚠️ **Run all `curl`s in an SSH session ON THE VM, against `localhost`.** The public
> URLs (`*.ahmedxsaad.me`) return **403 `cf-mitigated: challenge`** to `curl` — that is the
> Cloudflare bot challenge, **not** an outage. Browsers pass it; `localhost` bypasses it.
> Internal ports: remote `8080` · eval `8000` · flight `8001` · dashboard `3001`.

```bash
# Put the shared secret in an env var (value is in /srv/sentinel/.env on the VM):
export SEC="$(grep -E '^FORGE_REMOTE_SECRET=' /srv/sentinel/.env | head -1 | cut -d= -f2- | tr -d '\r')"
[ "${#SEC}" = 64 ] && echo "secret OK (64 chars)" || echo "!! SEC is empty/wrong -> every curl will return 'invalid or missing X-Sentinel-Secret'"

# 1) Health: all four must be 200 (localhost, NOT the public URL).
declare -A PORT=( [remote]=8080 [eval]=8000 [flight]=8001 )
for n in remote eval flight; do
  curl -s -o /dev/null -w "$n (:${PORT[$n]}): %{http_code}\n" http://127.0.0.1:${PORT[$n]}/health
done
curl -s -o /dev/null -w "dashboard (:3001): %{http_code}\n" http://127.0.0.1:3001
# dashboard in the BROWSER: https://dashboard.ahmedxsaad.me (browsers pass the CF challenge).

# 2) Pre-generate 3 runs so you can pick the one with the best story
#    (you WANT a 'fail' or 'uncertain' run — it files a Jira Incident and shows attribution).
for k in AO-11 AO-21 AO-51; do
  curl -s -XPOST http://127.0.0.1:8080/analyze \
    -H "X-Sentinel-Secret: $SEC" -H 'Content-Type: application/json' \
    -d "{\"incident_key\":\"$k\",\"requested_by\":\"demo\"}" \
  | jq -c '{incident:"'$k'", run_id, verdict:.eval_verdict.verdict, flagged:.eval_verdict.self_evaluation.flag_for_human}'
done
```

- 💡 From the output, **pick the `run_id` whose verdict is `fail` or `uncertain`** (best narrative). Call it `RID`. A `pass` + `flagged=true` also works (it filed a human-review issue) — just reword the verdict beat.
- 💡 **Live calls are working** — a Workers AI overflow account (`CF_AI_ACCOUNT_ID` / `CF_AI_API_TOKEN`) is set in `/srv/sentinel/.env`, giving a fresh ~10k-neuron/day budget; D1 stays on the primary. Verified: live `/embed` 200 and a full live `/analyze AO-11` 200.
- 💡 **If `/analyze` ever returns 503** (budget spent again), don't panic — demo from an already-recorded `RID` below; replay / verdict / trace need **zero** live calls.

**Ready-made fallback `run_id`s (recorded, work offline):**

| `run_id` | task | best for |
|---|---|---|
| `3df5e7ee23954b509c4af67e229bede0` | AO-31 | verdict **uncertain + flagged** — the "caught" story |
| `38f82299401d40f99e164d72386e1fb4` | AO-11 | fresh live run, **pass + flagged** (human-review issue) |
| `fbe8d4a387c940649cc0be4186f40a09` | AO-71 | has a **fail** trial (pass^k inconsistency) |

Bisect pair (same task, real divergence): good `3df5e7ee23954b509c4af67e229bede0` vs bad `419afe5fb3d64ade918b3af9ddce420a` (both AO-31).

**Open these browser tabs, in this order, before recording** (replace `RID`):
1. `https://dashboard.ahmedxsaad.me/`
2. `https://dashboard.ahmedxsaad.me/runs`
3. `https://dashboard.ahmedxsaad.me/runs/RID`
4. `https://dashboard.ahmedxsaad.me/replay/RID`
5. `https://dashboard.ahmedxsaad.me/verdicts/RID`
6. `https://dashboard.ahmedxsaad.me/reliability`
7. `https://ahmedains.atlassian.net/jira/...` → project **AO** issues (sorted newest first)
8. (optional) `https://langfuse.ahmedxsaad.me`
9. A terminal, large font, with the `curl` from step 2 ready to paste.

**Recording settings:** OBS / QuickTime · 1920×1080 · 30 fps · mic on · browser zoom 110–125% · incognito, no bookmark bar · `?mock=true` appended to any URL is your safety net if a page is slow.

---

## 1. Hook — the problem  ·  0:00–0:18

- ▶ Start on the **title slide** of `concept.pdf` (or dashboard `/`).
- 🎙 "Enterprises are putting AI agents into production, but agents are non-deterministic: they can look busy, call the right tools, and still get it wrong, and you only find out after a real ticket was touched. Sentinel is the reliability layer that catches that. Here it is on a real Atlassian incident agent."

---

## 2. UC3 — generate  ·  0:18–1:05

- ▶ Switch to the **terminal** (an SSH session on the VM). Paste and run the single `/analyze` curl for your chosen incident:
  ```bash
  curl -s -XPOST http://127.0.0.1:8080/analyze -H "X-Sentinel-Secret: $SEC" \
    -H 'Content-Type: application/json' -d '{"incident_key":"AO-11","requested_by":"demo"}' | jq .
  ```
- ▶ While it runs (~15–20s), keep talking. When it returns, point the cursor at `run_id`, `rca_draft`, and `eval_verdict`.
- 🎙 "Our Forge Rovo agent is built, deployed, and installed on this site. Here I trigger the exact backend it calls. The agent embeds the incident, runs semantic vector search over past incidents and runbooks, and an LLM drafts a structured root-cause analysis: a hypothesis, cited evidence, a proposed severity, and a confidence score. It is structured output, never free text, so everything downstream can score it."
- 💡 If budget is exhausted and it 503s, say: "triggering the recorded run" and skip to the dashboard with your pre-made `RID`.

---

## 3. UC2 — the flight recorder (trace)  ·  1:05–1:55

- ▶ Go to tab **`/runs`**. 🎙 "Every run the agent makes is recorded." ▶ Click your run row → lands on **`/runs/RID`**.
- ▶ Slowly scroll the step timeline. Point at each of the 4 steps.
- 🎙 "This is the agent's exact trajectory, taped live at the network boundary. Step zero: it embeds the incident. Steps one and two: it searches past incidents, then runbooks, in xqdrant. Step three: the LLM drafts the RCA. Each step shows the model, a readable preview, and is part of a hash-chained, signed audit trail, so this record is tamper-evident."

---

## 4. UC2 — deterministic replay  ·  1:55–2:40

- ▶ Go to tab **`/replay/RID`**. ▶ Click **Launch replay**. ▶ When it returns, point the cursor at **`live_call_count: 0`** and **`diverged: false`**.
- 🎙 "Now the part a log file can't do. We replay the exact run from tape. Zero live API calls, no divergence. That means we can debug an agent without re-sending an email or re-modifying a ticket. We can also bisect two runs to find the first step where they diverge, and inject a different response mid-replay to see how the agent's path changes."
- 💡 Optional: scroll to the bisect/inject panel and hover it for 2 seconds; don't run it unless you have time.

---

## 5. UC1 — the verdict  ·  2:40–3:35

- ▶ Go to tab **`/verdicts/RID`**. ▶ Point at the verdict (FAIL / UNCERTAIN / PASS), then the per-dimension scores, then the attribution box, then the self-critique + recommended action.
- 🎙 "The eval engine judged that recorded run. Not pass-fail on the text, but a multi-level evaluation: a safety filter, deterministic code checks, and a calibrated LLM judge. Here is the per-dimension breakdown, and crucially, the failure attribution: which step and which component is to blame, with a confidence. The judge also critiques itself and, because it was uncertain, flags it for a human. A non-AI engineer can read this and know exactly what to do."
- ▶ Switch to the **Jira AO** tab. Point at the newest **Incident** the eval engine auto-filed.
- 🎙 "And this lands in Atlassian automatically: the eval engine filed this Incident in Jira for the flagged run."
- 💡 If your chosen run PASSED, reword: "It passed safety, the code grader, and the judge, with these dimension scores," and skip the Jira-incident line (or show a previously filed one).

---

## 6. Rigour — reliability over many runs  ·  3:35–4:25

- ▶ Go to tab **`/reliability`**. ▶ Point at the pass^k numbers, then the Cohen's κ panel, then drift.
- 🎙 "One run isn't reliability. We use pass-to-the-k, the tau-bench metric: a task only passes if all eight independent trials pass. Across our set, pass-at-one is one hundred percent but pass-to-the-eight collapses, that gap is the inconsistency a single run hides, and the single number that tells a platform owner this agent isn't ready to run unattended. We also evaluate the evaluator itself with Cohen's kappa against human labels, and detect drift in pass rate, dimension scores, and output style over time."

---

## 7. Explainability / audit  ·  4:25–4:50  (optional, cut first if over time)

- ▶ Switch to **Langfuse** tab (or back to the trace's audit section). Scroll one trace.
- 🎙 "Everything is traceable end to end. Every LLM call and vector search is also exported to Langfuse for an engineer who wants the raw prompts, responses, and latencies. Evidence, confidence, decision trace, and a tamper-evident audit: explanation by construction, not a panel bolted on."

---

## 8. Close  ·  4:50–5:00

- ▶ Cut to the **closing slide** of `concept.pdf` (or dashboard `/`).
- 🎙 "Three services live on Azure, a Forge agent installed on Jira and Confluence, and this dashboard. Reliability infrastructure, dogfooded on a real Atlassian agent. Thank you."

---

## If something breaks mid-take
- A page is slow / shows MOCK fallback → append **`?mock=true`** to the URL; it renders instantly with realistic fixtures. Say "demo data" if asked; switch back to live after.
- `/analyze` 503 (CF budget) → narrate over the **pre-recorded `RID`**; replay/verdict/trace need no live calls.
- Don't restart services on camera. If one is down, fix it before recording (`sudo systemctl restart sentinel-<svc>`).

## One beat you must not miss
The **"looked fine → caught"** contrast: the RCA posted successfully, yet the verdict is FAIL/UNCERTAIN with the exact step blamed and a Jira Incident filed. Linger on that for 3 seconds. It is the entire pitch.

## Post-production checklist
- [ ] Total length **under 5:00** (hard limit).
- [ ] 2-second title card at start, 2-second "github.com/ahmedxsaad/AINS" card at end.
- [ ] Trim dead air during the `/analyze` wait (or speed-ramp 4×).
- [ ] Captions/subtitles if time allows (judges may watch muted).
- [ ] Export 1080p MP4, check audio levels once end-to-end.
