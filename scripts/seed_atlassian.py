#!/usr/bin/env python3
"""
seed_atlassian.py — Seed the Atlassian dev site with synthetic data.

Creates:
  - 1 Jira project (key: SENT)
  - 1 JSM service desk
  - 100 synthetic incidents across 10 root-cause categories
  - 20 Confluence runbook pages across 10 categories

Usage:
    make seed
    # or directly:
    python scripts/seed_atlassian.py

Requires: ATLASSIAN_SITE, ATLASSIAN_EMAIL, ATLASSIAN_API_TOKEN in .env
"""

import base64
import json
import os
import time
from dataclasses import dataclass

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

SITE  = os.environ["ATLASSIAN_SITE"]
EMAIL = os.environ["ATLASSIAN_EMAIL"]
TOKEN = os.environ["ATLASSIAN_API_TOKEN"]
AUTH  = base64.b64encode(f"{EMAIL}:{TOKEN}".encode()).decode()

HEADERS = {
    "Authorization": f"Basic {AUTH}",
    "Content-Type":  "application/json",
    "Accept":        "application/json",
}

JIRA_URL       = f"{SITE}/rest/api/3"
CONFLUENCE_URL = f"{SITE}/wiki/rest/api"

# ── Synthetic Data ─────────────────────────────────────────────────────────────

# 10 root-cause categories × 10 incidents each = 100 total
# Each category has varied phrasings to test semantic similarity detection

INCIDENT_CATEGORIES = [
    {
        "root_cause": "database_connection_pool",
        "runbook_title": "Database Connection Pool Exhaustion",
        "incidents": [
            ("DB connection pool exhausted on prod",
             "All database connections consumed. App servers queuing requests. DB CPU at 95%."),
            ("Cannot connect to database — pool full",
             "Connection timeout errors in application logs. Pool size limit reached."),
            ("Database unavailable — connection limit hit",
             "Services reporting DB unavailability. Connection count maxed out at 500."),
            ("Prod DB connections maxed out",
             "Health checks failing. Application unable to acquire DB connections."),
            ("Database pool overflow causing timeouts",
             "Request latency spike. Root cause appears to be DB connection saturation."),
            ("DB connection refused — max connections exceeded",
             "Error: too many connections. Database server rejecting new connections."),
            ("Service degradation — database connections exhausted",
             "Multiple services degraded. Shared DB connection pool full."),
            ("Database connection saturation — prod environment",
             "Connection pool metrics show 100% utilization since 14:30 UTC."),
            ("DB pool limit causing request failures",
             "5xx errors on all database-dependent endpoints."),
            ("Connection pool exhaustion cascading to all services",
             "Cascading failures traced to connection pool depletion."),
        ],
    },
    {
        "root_cause": "memory_leak",
        "runbook_title": "Memory Leak in Application Services",
        "incidents": [
            ("Memory leak in payment service after v2.3.1 deploy",
             "Heap growing steadily since deployment at 09:00 UTC. Service restarted twice."),
            ("Heap memory climbing on order-service",
             "JVM heap usage increasing 50MB/hour. No GC reclaiming memory."),
            ("OOM errors on API gateway",
             "Out-of-memory kills on pod. Restart loop. Likely memory leak."),
            ("Memory usage trending up since last release",
             "No load increase but memory consumption growing consistently."),
            ("Service pod getting OOM killed repeatedly",
             "Kubernetes OOM killer terminating pods every 4 hours."),
            ("Gradual memory growth causing service crashes",
             "Memory profiling shows retained objects accumulating in request handler."),
            ("JVM heap exhaustion — user-service",
             "FullGC events increasing. Heap utilization at 98%."),
            ("Memory leak suspected in notification service",
             "RSS memory growing 200MB/day. Service restarted as mitigation."),
            ("Heap dump analysis shows memory retention",
             "Thread-local storage objects not being freed after request completion."),
            ("Application memory exhaustion after 48h uptime",
             "Memory usage normal at start, grows to OOM after ~48 hours of uptime."),
        ],
    },
    {
        "root_cause": "api_gateway_502",
        "runbook_title": "API Gateway 502 Bad Gateway Errors",
        "incidents": [
            ("API gateway returning 502 errors on /checkout",
             "Multiple customers reporting checkout failures. Error logs show upstream timeout."),
            ("502 errors on payment endpoints",
             "Upstream payment service not responding within gateway timeout."),
            ("Intermittent 502 from load balancer",
             "5% of requests returning 502. Upstream pods appear healthy."),
            ("Gateway timeout causing customer-facing errors",
             "Upstream response time exceeding 30s gateway timeout threshold."),
            ("Bad gateway errors on product search",
             "Search service returning 502 from gateway perspective."),
            ("Upstream connection refused — 502 spike",
             "Gateway reporting upstream connection refused on 3 of 5 pods."),
            ("502 errors after deployment of v4.1.0",
             "502s started immediately after deploy. Rollback restored service."),
            ("API gateway health check failures",
             "Upstream health checks failing. Gateway marking backends unhealthy."),
            ("502 Bad Gateway on all /api/v2 endpoints",
             "Scoped to v2 endpoints only. v1 unaffected. Upstream configuration issue."),
            ("Gateway upstream pool depleted",
             "All upstream connections in use. Gateway returning 502 on new requests."),
        ],
    },
    {
        "root_cause": "disk_full",
        "runbook_title": "Disk Space Exhaustion",
        "incidents": [
            ("Disk full on prod DB server",
             "PostgreSQL stopped writing. Disk at 100%. Logs consuming all space."),
            ("Storage volume full — application crashing",
             "Write failures. Application reporting disk full errors."),
            ("Log rotation failed — disk exhausted",
             "Log files grew unchecked. Disk full. Services unable to write."),
            ("No disk space left on /var/log partition",
             "/var/log at 100%. Syslog not rotating. Application health degraded."),
            ("Disk space alert — 95% on primary volume",
             "Primary EBS volume at 95%. Risk of service disruption imminent."),
            ("Database transaction log filling disk",
             "Transaction logs not being purged. Disk approaching full."),
            ("Container disk exhaustion causing pod failure",
             "Ephemeral storage limit hit. Pod evicted by kubelet."),
            ("Write failures — file system full",
             "ENOSPC errors in application logs. File system write operations failing."),
            ("Temporary files accumulating on /tmp",
             "/tmp partition full. Application unable to create temporary files."),
            ("Disk I/O errors following space exhaustion",
             "Cascading I/O errors after disk filled up during batch job."),
        ],
    },
    {
        "root_cause": "high_cpu",
        "runbook_title": "High CPU Utilization",
        "incidents": [
            ("CPU at 100% on web servers",
             "All web server CPUs pegged at 100%. Response times spiking."),
            ("CPU spike causing service degradation",
             "Unexpected CPU spike to 95%. Correlated with new traffic pattern."),
            ("Runaway process consuming all CPU",
             "Single process consuming 90% CPU. PID identified, investigating."),
            ("High CPU after batch job started",
             "Scheduled batch job consuming excessive CPU. Other services impacted."),
            ("CPU throttling on container instances",
             "Kubernetes CPU throttling metrics elevated. Pod performance degraded."),
            ("Infinite loop causing CPU exhaustion",
             "Code change introduced infinite loop. CPU at 100% on affected pods."),
            ("CPU saturation on database server",
             "DB CPU at 100%. Long-running query identified as cause."),
            ("Crypto mining process detected — high CPU",
             "Unauthorized process consuming CPU. Security incident suspected."),
            ("CPU spike correlated with traffic increase",
             "CPU proportional to traffic but algorithm not scaling efficiently."),
            ("Background job consuming CPU in production",
             "Backfill job impacting production. CPU contention with API servers."),
        ],
    },
    {
        "root_cause": "ssl_certificate",
        "runbook_title": "SSL Certificate Issues",
        "incidents": [
            ("SSL certificate expired on api.example.com",
             "Certificate expired at midnight. All HTTPS requests failing."),
            ("TLS handshake failures on customer portal",
             "Clients reporting TLS errors. Certificate validity check failing."),
            ("HTTPS broken — certificate chain incomplete",
             "Intermediate certificate missing. Browser SSL errors reported by users."),
            ("Certificate expiry causing authentication failures",
             "Auth service certificate expired. Login flow broken."),
            ("SSL warning: certificate expires in 3 days",
             "Certificate expiry imminent. Renewal process not triggered automatically."),
            ("Mixed content errors after cert renewal",
             "New certificate installed but some resources still serving over HTTP."),
            ("Certificate mismatch on load balancer",
             "Certificate installed on LB doesn't match domain. Handshake failing."),
            ("Wildcard cert expired affecting multiple services",
             "Wildcard *.example.com expired. All subdomains affected."),
            ("OCSP stapling failure causing slow connections",
             "OCSP responder unreachable. Slow SSL handshakes."),
            ("Self-signed cert detected in production",
             "Self-signed certificate deployed to production by mistake."),
        ],
    },
    {
        "root_cause": "network_latency",
        "runbook_title": "Network Latency and Connectivity Issues",
        "incidents": [
            ("High latency between services in us-east-1",
             "Inter-service latency elevated to 500ms. Normal is <10ms."),
            ("Network packet loss causing timeouts",
             "1% packet loss causing cascading timeouts across services."),
            ("Cross-region latency spike",
             "EU to US latency increased 10x. DNS propagation suspected."),
            ("Service mesh latency anomaly",
             "Envoy proxy showing elevated latency on specific route."),
            ("BGP route change causing traffic rerouting",
             "ISP BGP change rerouting traffic via longer path. Latency increased."),
            ("MTU mismatch causing fragmentation",
             "Large packets being fragmented. Performance degraded."),
            ("VPN tunnel instability",
             "Site-to-site VPN reconnecting frequently. Services relying on it affected."),
            ("DNS resolution latency elevated",
             "DNS lookups taking 2s instead of <10ms. Upstream resolver issue."),
            ("Network congestion in availability zone",
             "AZ-level network congestion. Traffic shifted to other AZs."),
            ("Firewall rule blocking inter-service traffic",
             "New firewall rule accidentally blocking service-to-service calls."),
        ],
    },
    {
        "root_cause": "deployment_failure",
        "runbook_title": "Deployment Failures and Rollback Procedures",
        "incidents": [
            ("Production deployment failed — service down",
             "v3.2.0 deployment failed. Rollback initiated. Root cause under investigation."),
            ("Config map update broke service startup",
             "Wrong configuration deployed. Services failing to start with config error."),
            ("Database migration failed during deployment",
             "Schema migration failed at step 3. Deployment halted. DB in inconsistent state."),
            ("Container image pull failure in production",
             "Image registry unreachable during deployment. Pods stuck in ImagePullBackOff."),
            ("Deployment caused dependency version conflict",
             "Library version mismatch introduced by deployment. Runtime errors."),
            ("Health check failures after deployment",
             "New version failing health checks. Deployment rollback in progress."),
            ("Zero-downtime deployment not working as expected",
             "Traffic routed to new version before it was ready. Brief outage."),
            ("Helm chart misconfiguration in production deploy",
             "Wrong values.yaml used. Services started with incorrect resource limits."),
            ("Blue-green switch caused connection drops",
             "Traffic switch between blue and green caused connection reset errors."),
            ("Feature flag misconfiguration after deploy",
             "Feature flag service not updated before deployment. Inconsistent behavior."),
        ],
    },
    {
        "root_cause": "queue_backlog",
        "runbook_title": "Message Queue Backlog and Consumer Lag",
        "incidents": [
            ("Kafka consumer lag growing on order-processor",
             "Consumer group lag reached 1M messages. Processing falling behind."),
            ("Message queue backlog causing order delays",
             "Queue depth growing. Consumers not keeping up with producer rate."),
            ("Dead letter queue filling up",
             "DLQ accumulating failed messages. Root cause: downstream service down."),
            ("RabbitMQ memory threshold triggered",
             "RabbitMQ pausing publishers due to memory threshold hit."),
            ("Consumer group rebalancing causing processing halt",
             "Kafka rebalance storm. Consumers repeatedly joining and leaving."),
            ("SQS queue depth exceeding alarm threshold",
             "SQS queue depth at 500k messages. Lambda concurrency at limit."),
            ("Message processing timeout causing requeue",
             "Processing time exceeding visibility timeout. Messages requeued."),
            ("Duplicate message processing detected",
             "Consumers processing messages multiple times. Idempotency issue."),
            ("Queue subscriber crash causing backlog",
             "Subscriber pod crashed. Messages accumulating with no consumers."),
            ("Message size limit exceeded on queue",
             "Large messages rejected by queue. Producers failing silently."),
        ],
    },
    {
        "root_cause": "authentication_failure",
        "runbook_title": "Authentication and Authorization Failures",
        "incidents": [
            ("JWT tokens expiring too quickly",
             "Users being logged out unexpectedly. Token TTL misconfigured to 1 minute."),
            ("Auth service returning 401 for valid sessions",
             "Authenticated users getting 401. Session store inconsistency suspected."),
            ("OAuth callback URL mismatch",
             "OAuth flow broken. Redirect URI not matching registered callback."),
            ("API key rotation broke service authentication",
             "Service-to-service auth failing after API key rotation. Key not propagated."),
            ("Session invalidation not working correctly",
             "Users able to access resources after logout. Session not cleared properly."),
            ("Auth rate limiting too aggressive",
             "Legitimate users being rate limited on login. Threshold too low."),
            ("SAML assertion validation failing",
             "SSO login broken. SAML assertion signature validation error."),
            ("Service account credentials expired",
             "Background job failing. Service account password expired."),
            ("MFA bypass vulnerability detected",
             "Security team identified MFA bypass. Immediate investigation required."),
            ("Token refresh endpoint returning 500",
             "Token refresh failing. Users unable to maintain sessions."),
        ],
    },
]

# ── Confluence Runbook Template ───────────────────────────────────────────────

def make_runbook_body(category: dict) -> str:
    """Generate ADF content for a Confluence runbook page."""
    return json.dumps({
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": "Overview"}]
            },
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": f"This runbook covers diagnosis and remediation procedures for {category['runbook_title'].lower()} incidents."}]
            },
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": "Detection"}]
            },
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": f"This issue is typically detected via monitoring alerts, increased error rates, or customer reports. Root cause: {category['root_cause'].replace('_', ' ')}."}]
            },
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": "Diagnosis Steps"}]
            },
            {
                "type": "orderedList",
                "content": [
                    {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Check monitoring dashboards for relevant metrics."}]}]},
                    {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Review recent deployments and configuration changes."}]}]},
                    {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Check application and infrastructure logs for error patterns."}]}]},
                    {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Verify external dependencies and third-party service status."}]}]},
                ]
            },
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": "Remediation"}]
            },
            {
                "type": "orderedList",
                "content": [
                    {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Implement immediate mitigation to restore service."}]}]},
                    {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Address root cause to prevent recurrence."}]}]},
                    {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Document findings and create follow-up action items."}]}]},
                ]
            },
        ]
    })


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def post(url: str, data: dict, retries: int = 5) -> dict:
    """POST with exponential backoff on 429."""
    for attempt in range(retries):
        r = requests.post(url, headers=HEADERS, json=data)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 2 ** attempt))
            print(f"  [rate limit] waiting {wait}s...")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"POST {url} failed after {retries} retries")


def get(url: str) -> dict:
    """GET with basic error handling."""
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()


# ── Main ──────────────────────────────────────────────────────────────────────

def get_or_create_confluence_space() -> str:
    """Get the SENT Confluence space key, creating it if needed."""
    try:
        result = get(f"{CONFLUENCE_URL}/space/SENT")
        print("✓ Confluence space SENT already exists")
        return "SENT"
    except Exception:
        pass

    print("→ Creating Confluence space SENT...")
    result = post(f"{CONFLUENCE_URL}/space", {
        "key": "SENT",
        "name": "Sentinel Runbooks",
        "description": {
            "plain": {"value": "Incident runbooks for Sentinel demo.", "representation": "plain"}
        }
    })
    print("✓ Confluence space created")
    return result["key"]


def seed_runbooks(space_key: str) -> None:
    """Create one Confluence runbook page per incident category."""
    print(f"\n→ Seeding {len(INCIDENT_CATEGORIES)} Confluence runbooks...")
    for category in INCIDENT_CATEGORIES:
        post(f"{CONFLUENCE_URL}/content", {
            "type": "page",
            "title": f"Runbook: {category['runbook_title']}",
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": make_runbook_body(category),
                    "representation": "atlas_doc_format"
                }
            }
        })
        print(f"  ✓ {category['runbook_title']}")
        time.sleep(0.5)  # gentle pacing


def seed_incidents(project_key: str) -> None:
    """Create 100 synthetic JSM incidents."""
    print(f"\n→ Seeding 100 incidents into project {project_key}...")
    count = 0
    for category in INCIDENT_CATEGORIES:
        for summary, description in category["incidents"]:
            post(f"{JIRA_URL}/issue", {
                "fields": {
                    "project": {"key": project_key},
                    "summary": summary,
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [{
                            "type": "paragraph",
                            "content": [{"type": "text", "text": description}]
                        }]
                    },
                    "issuetype": {"id": "10013"},
                }
            })
            count += 1
            print(f"  [{count:3d}/100] {summary[:60]}")
            time.sleep(0.3)  # stay well within rate limits


def main() -> None:
    print("=== Sentinel: Atlassian Dev Site Seeder ===")
    print(f"Site: {SITE}")
    print()

    project_key = os.environ.get("ATLASSIAN_JIRA_PROJECT_KEY", "SENT")
    space_key   = get_or_create_confluence_space()

    pass  # runbooks already seeded
    seed_incidents(project_key)

    print()
    print("=== Seeding complete ===")
    print(f"  Runbooks: {len(INCIDENT_CATEGORIES)} Confluence pages created")
    print("  Incidents: 100 Jira issues created")
    print()
    print("Next step: run the atlassian-agent against these incidents, then `make eval`")


if __name__ == "__main__":
    main()
