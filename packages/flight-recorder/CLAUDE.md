# flight-recorder / CLAUDE.md

> Read the root `CLAUDE.md` first, especially Section 0 (deployed infra).
> This package runs on the Azure VM at port 8001, exposed at `flight.ahmedxsaad.me`.

## What This Package Does

**UC2: The flight recorder for AI agents.**
Transparently intercepts every LLM call and tool call, stores the full trace,
and enables deterministic replay without touching live APIs.

## Key Files

> **Layout:** standard src-layout — the importable package is
> `src/flight_recorder/`, imported as `from flight_recorder.proxy.cassette import ...`
> (repo convention; on-disk path == import path keeps `mypy --strict` clean). `api.py`
> lives at the package root and is run with `uvicorn api:app --port 8001`.

```
flight-recorder/
├── api.py                        FastAPI server (port 8001): /runs /replay /bisect /health
├── pyproject.toml                hatchling package; deps: trace-core, httpx, boto3, fastapi
├── src/flight_recorder/
│   ├── config.py                 FLIGHT_MODE resolution, CF-URL detection, genesis hash
│   ├── exceptions.py             CassetteMissError (replay never falls back to a live call)
│   ├── proxy/
│   │   ├── llm_proxy.py          RecordingTransport — httpx transport, intercepts CF AI calls
│   │   ├── mcp_interceptor.py    @record_tool decorator — tool/function call interceptor
│   │   └── cassette.py           cassette read/write + request normalization (reuses trace_core)
│   ├── replay/
│   │   ├── engine.py             replay_run() — re-executes with replay transport, 0 live calls
│   │   └── bisect.py             bisect_runs() — first diverging step between two runs
│   ├── storage/
│   │   ├── d1_client.py          trace metadata → Cloudflare D1 REST API
│   │   └── minio_client.py       cassette blobs → MinIO (NOT R2)
│   └── audit/
│       └── hash_chain.py         write_audit_record() — hash-chained HMAC receipts
└── tests/                        test_cassette/llm_proxy/hash_chain/replay/mcp_interceptor/bisect
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
make test-uc2                                      # pytest + coverage for this package
uv run mypy packages/flight-recorder               # mypy --strict (config in root pyproject)
uv run ruff check packages/flight-recorder
FLIGHT_MODE=replay uv run uvicorn api:app --port 8001   # run the API (from this dir)
```

Programmatic usage (record then replay, asserting zero live calls):

```python
import httpx
from flight_recorder import RecordingTransport, replay_run

run_id = "..."
# record: drive the agent with a recording client
client = httpx.Client(transport=RecordingTransport(run_id, mode="record"))
agent(client)            # every CF Workers AI call is taped into the cassette
# replay: re-run against the cassette — RecordingTransport(mode="replay")
result = replay_run(run_id, agent)
assert result.live_call_count == 0
```