# Sentinel — System Architecture

---

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ATLASSIAN CLOUD                                     │
│                                                                             │
│   JSM Incident (webhook trigger)                                            │
│          │                                                                  │
│          ▼                                                                  │
│   ┌─────────────────────────────────────────────────────┐                  │
│   │         packages/atlassian-agent  (Forge)           │                  │
│   │         TypeScript · Rovo Agent + Actions           │                  │
│   │                                                     │                  │
│   │  fetch-incident → search-similar → search-runbooks  │                  │
│   │  post-rca-comment → draft-pir-page                  │                  │
│   └──────────────────────┬──────────────────────────────┘                  │
