import sys
import os

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Any

from api.orchestrator import run_pipeline, get_trace, list_runs

app = FastAPI(title="AINS UC3 — FAQ Pipeline", version="1.0.0")


# ─────────────────────────────────────────
# Webhook payload models
# ─────────────────────────────────────────

class JiraWebhookPayload(BaseModel):
    """
    Minimal model for a Jira issue_updated webhook.
    Jira sends a lot more — we only need the issue key.
    """
    issue: dict[str, Any]


class ManualTrigger(BaseModel):
    ticket_id: str


# ─────────────────────────────────────────
# Routes
# ─────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook")
async def jira_webhook(payload: JiraWebhookPayload, background_tasks: BackgroundTasks):
    """
    Receives Jira automation webhook on issue resolution.
    Fires the pipeline in the background so Jira doesn't time out.
    """
    try:
        ticket_id = payload.issue["key"]
    except (KeyError, TypeError):
        raise HTTPException(status_code=400, detail="Missing issue.key in payload")

    # Only process tickets that are actually resolved
    status = (
        payload.issue.get("fields", {})
        .get("status", {})
        .get("statusCategory", {})
        .get("key", "")
    )
    if status != "done":
        return {"skipped": True, "reason": "ticket not in Done status"}

    background_tasks.add_task(run_pipeline, ticket_id)
    return {"accepted": True, "ticket_id": ticket_id}


@app.post("/run")
def manual_run(body: ManualTrigger):
    """
    Manual trigger for testing without a real Jira webhook.
    Blocks until the pipeline completes and returns the result.
    """
    try:
        result = run_pipeline(body.ticket_id)
        return {"run_id": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/trace/{run_id}")
def trace(run_id: str):
    """Return the full execution trace for a pipeline run."""
    events = get_trace(run_id)
    if not events:
        raise HTTPException(status_code=404, detail=f"No trace found for run_id={run_id}")
    return {"run_id": run_id, "events": events}


@app.get("/traces")
def traces():
    """List recent pipeline runs."""
    return {"runs": list_runs()}
