# MCP Audit Trail — Specification Proposal

**Status:** Draft · **Authors:** Sentinel team · **Hackathon:** AINS 2026

---

## Problem Statement

The [Model Context Protocol (MCP)](https://spec.modelcontextprotocol.io/) defines how AI agents call external tools via a standardized JSON-RPC protocol. It does not define:

1. **A standard audit trail format.** There is no standardized way to record what tools an agent called, with what arguments, at what time, in a form that is verifiable and tamper-evident.

2. **Authorization propagation through gateways.** When an MCP call passes through an intermediary (a gateway, a replay proxy, a load balancer), there is no standard for preserving the original caller's identity in the audit log.

This creates a security and compliance gap: enterprise deployments cannot prove what an agent did, when, or on whose behalf.

---

## Proposed Audit Record Format

Each MCP tool call generates one append-only audit record written **before** the call executes (write-ahead):

```json
{
  "schema_version": 1,
  "record_type": "mcp_tool_call",
  "run_id": "uuid-of-the-agent-run",
  "step_id": "uuid-of-this-step",
  "sequence": 7,
  "timestamp_before_call": "2026-06-15T14:32:01.123Z",
  "tool": {
    "name": "create_jira_issue",
    "server": "atlassian-rovo-mcp",
    "version": "1.0.0"
  },
  "caller": {
    "agent_id": "incident-rca-agent",
    "account_id": "5f8a3b2c..."
  },
  "input": {
    "summary": "...",
    "description": "..."
  },
  "audit_chain": {
    "prev_hash": "sha256:abc123...",
    "payload_hash": "sha256:def456...",
    "hmac": "sha256:ghi789..."
  }
}
```

After the call completes (or fails), a second record appends the result:

```json
{
  "record_type": "mcp_tool_result",
  "step_id": "same-uuid-as-above",
  "timestamp_after_call": "2026-06-15T14:32:01.890Z",
  "latency_ms": 767,
  "status": "success",
  "output": { "issue_key": "SENT-42" },
  "audit_chain": {
    "prev_hash": "sha256:ghi789...",
    "payload_hash": "sha256:jkl012...",
    "hmac": "sha256:mno345..."
  }
}
```

---

## Tamper-Evidence via Hash Chaining

Records form a hash chain: each record's `prev_hash` is the `payload_hash` of the previous record. An HMAC signed with a server-side key makes individual records tamper-evident.

**Verification:** to verify the integrity of a run's audit log, recompute each record's `payload_hash` and verify the chain is unbroken, then verify each HMAC. If any record was modified, the chain breaks at that point.

---

## Reference Implementation

`packages/flight-recorder/audit/hash_chain.py` — `write_audit_record()` implements this format.

---

## Open Questions

1. Should the HMAC key be per-deployment or per-run?
2. What is the standard storage format — JSONL file, database, or both?
3. How should audit records be exposed to compliance tooling — a standardized MCP resource endpoint?
