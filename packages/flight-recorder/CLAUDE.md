# flight-recorder / CLAUDE.md

> Read the root `CLAUDE.md` first, especially Section 0 (deployed infra).
> This package runs on the Azure VM at port 8001, exposed at `flight.ahmedxsaad.me`.

## What This Package Does

**UC2: The flight recorder for AI agents.**
Transparently intercepts every LLM call and tool call, stores the full trace,
and enables deterministic replay without touching live APIs.

## Key Files

```
flight-recorder/
├── src/
│   ├── proxy/
│   │   ├── llm_proxy.py          httpx transport override — intercepts CF Workers AI calls
│   │   ├── mcp_interceptor.py    decorator-based tool call interceptor
│   │   └── cassette.py           cassette read/write + request normalization
│   ├── replay/
│   │   ├── engine.py             replay orchestrator
│   │   └── bisect.py             find first diverging step between two runs
│   ├── storage/
│   │   ├── d1_client.py          trace metadata → Cloudflare D1
│   │   └── minio_client.py       trace blobs → MinIO (NOT R2)
│   └── audit/
│       └── hash_chain.py         write_audit_record() — hash-chained HMAC receipts
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/                 pre-recorded cassettes for deterministic tests
```

## Blob Storage — MinIO (NOT Cloudflare R2)

> R2 was skipped — requires credit card. MinIO is S3-compatible and runs inside
> the Langfuse Docker stack on port 9090.

```python
import boto3, os

def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["BLOB_STORAGE_ENDPOINT"],       # http://localhost:9090
        aws_access_key_id=os.environ["BLOB_STORAGE_ACCESS_KEY"],     # minio
        aws_secret_access_key=os.environ["BLOB_STORAGE_SECRET_KEY"], # miniosecret
        region_name="us-east-1",  # required by boto3, value doesn't matter for MinIO
    )

BUCKET = os.environ["BLOB_STORAGE_BUCKET"]  # sentinel-cassettes

def store_blob(key: str, data: bytes) -> None:
    get_s3_client().put_object(Bucket=BUCKET, Key=key, Body=data)

def load_blob(key: str) -> bytes:
    return get_s3_client().get_object(Bucket=BUCKET, Key=key)["Body"].read()
```

## LLM Proxy — CF Workers AI

The proxy intercepts calls to CF Workers AI (not Anthropic). The URL pattern is:
```
https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}
```

```python
class RecordingTransport(httpx.BaseTransport):
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        step_key = hash_request(request)  # normalize + hash
        if self.mode == "replay" and step_key in self.cassette:
            return build_response(self.cassette[step_key])
        response = self._forward(request)
        if self.mode == "record":
            self.cassette[step_key] = response.json()
            write_audit_record(step_key, request, response)
        return response
```

## Audit Records — Write-Ahead Before Execution

```python
def write_audit_record(step_id, kind, input_data, output_data, prev_hash):
    """Hash-chained HMAC-signed receipt. Written BEFORE execution."""
    import hmac, hashlib, json
    payload = {"run_id": current_run_id, "step_id": step_id, "kind": kind,
               "input": input_data, "output": output_data, "prev_hash": prev_hash}
    payload_str = json.dumps(payload, sort_keys=True)
    sig = hmac.new(os.environ["AUDIT_HMAC_KEY"].encode(),
                   payload_str.encode(), hashlib.sha256).hexdigest()
    payload["hmac"] = sig
    # Write to D1 BEFORE the actual call
    d1_client.insert("trace_records", payload)
    return hashlib.sha256(payload_str.encode()).hexdigest()
```

## Critical Rules

- **Blob storage is MinIO** — use boto3 with `endpoint_url=http://localhost:9090`, never S3 directly
- **FLIGHT_MODE env var controls behavior** — `record | replay | passthrough`
- **Audit records are written BEFORE execution** (write-ahead logging)
- **Step key normalization strips ephemeral values** (timestamps, UUIDs) before hashing

## Known Gotchas

- Timestamps and UUIDs in prompts cause cassette misses — strip them in `cassette.py:normalize_request()`
- MinIO requires `region_name` in boto3 config even though it's ignored — use `us-east-1`
- The cassette format is versioned by `CASSETTE_VERSION` — bumping it breaks old cassettes

## Commands

```bash
make test-uc2
FLIGHT_MODE=record uv run python -m sentinel.flight_recorder.record --agent my_agent
FLIGHT_MODE=replay uv run python -m sentinel.flight_recorder.replay --run-id <uuid>
FLIGHT_MODE=replay uv run python -m sentinel.flight_recorder.bisect --good <uuid> --bad <uuid>
```