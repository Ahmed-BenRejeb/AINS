"""httpx transport overrides that intercept Cloudflare Workers AI calls.

Drop :class:`RecordingTransport` into any ``httpx.Client`` (or
:class:`AsyncRecordingTransport` into an ``httpx.AsyncClient``) and every CF
Workers AI ``run`` call flows through it. Behaviour is governed by ``FLIGHT_MODE``:

* ``record``      — forward the call, store the response in the cassette, append
                    the step's full ``TraceRecord``, and write an audit record.
* ``replay``      — return the stored response from the cassette; never call out.
                    A request with no recorded response raises
                    :class:`~flight_recorder.exceptions.CassetteMissError`.
* ``passthrough`` — forward only; record nothing.

Non-CF requests always pass straight through, so the transports are transparent
to unrelated traffic. Usage::

    client = httpx.Client(transport=RecordingTransport(run_id="uuid"))
    aclient = httpx.AsyncClient(transport=AsyncRecordingTransport(run_id="uuid"))

The two transports differ only in how they forward a live call (sync vs. async);
all record/replay/serialization logic lives once in :class:`_RecordingCore`.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from trace_core import FlightMode

from ..audit.hash_chain import sign, write_audit_record
from ..config import (
    CF_AI_RUN_PATH_MARKER,
    GENESIS_PREV_HASH,
    is_cf_workers_ai_url,
    resolve_mode,
)
from ..exceptions import CassetteMissError
from . import cassette


class _RecordingCore:
    """Shared record/replay logic for the sync and async recording transports.

    Subclasses provide only the transport-specific *forward* (one live call) and
    the httpx entry point (``handle_request`` / ``handle_async_request``); every
    cassette write, audit-chain link, and response (de)serialization is here so
    the two transports stay byte-for-byte consistent.
    """

    run_id: str
    mode: FlightMode
    _prev_hash: str
    _sequence: int
    live_call_count: int

    def _init_recording(self, run_id: str, mode: FlightMode | None) -> None:
        """Initialise the per-run recording state (called by each subclass)."""
        self.run_id = run_id
        self.mode = resolve_mode(mode)
        self._prev_hash = GENESIS_PREV_HASH
        self._sequence = 0
        self.live_call_count = 0
        """Number of calls actually forwarded to the network — must be 0 in replay."""

    @property
    def step_count(self) -> int:
        """Number of CF Workers AI calls recorded into the cassette so far."""
        return self._sequence

    def _persist(self, request: httpx.Request, step_key: str, stored: dict[str, Any]) -> None:
        """Tape one captured response: cassette ``steps`` + ``records`` + audit.

        Writes the audit record first (write-ahead), then stores the response and
        the step's full ``TraceRecord`` in the cassette under ``step_key``.
        """
        prev_hash = self._prev_hash
        step_id = uuid.uuid4().hex
        input_payload = self._request_payload(request, step_key)
        self._prev_hash = write_audit_record(
            run_id=self.run_id,
            step_id=step_id,
            kind="llm_call",
            input_data=input_payload,
            output_data=stored,
            prev_hash=prev_hash,
            sequence=self._sequence,
        )
        record = self._build_record(request, step_id, input_payload, stored, prev_hash)
        cassette.save_to_cassette(self.run_id, step_key, stored, record=record)
        self._sequence += 1

    def _build_record(
        self,
        request: httpx.Request,
        step_id: str,
        input_payload: dict[str, Any],
        stored: dict[str, Any],
        prev_hash: str,
    ) -> dict[str, Any]:
        """Build the step's full ``TraceRecord`` (JSON-mode dict) for the cassette.

        The CF Workers AI model is the URL path suffix after ``/ai/run/``; it is
        surfaced as ``metadata.model_id`` so the eval engine's transcript names the
        real model. The audit block reuses the just-written record's hashes.
        """
        model = request.url.path.split(CF_AI_RUN_PATH_MARKER, 1)[-1] or None
        return {
            "run_id": self.run_id,
            "step_id": step_id,
            "sequence": self._sequence,
            "timestamp": datetime.now(UTC).isoformat(),
            "kind": "llm_call",
            "input": input_payload,
            "output": stored,
            "metadata": {"model_id": model},
            "audit": {
                "prev_hash": prev_hash,
                "payload_hash": self._prev_hash,
                "hmac": sign(self._prev_hash),
            },
        }

    def _replay(self, request: httpx.Request, step_key: str) -> httpx.Response:
        """Return the recorded response for ``step_key`` without any live call."""
        steps = cassette.load_cassette(self.run_id)["steps"]
        if step_key not in steps:
            raise CassetteMissError(step_key)
        return self._rebuild_response(steps[step_key], request)

    @staticmethod
    def _serialize_response(response: httpx.Response) -> dict[str, Any]:
        """Capture a (already-read) response as a JSON-serializable cassette dict."""
        try:
            body: Any = response.json()
            is_json = True
        except json.JSONDecodeError:
            body = response.text
            is_json = False
        return {
            "status_code": response.status_code,
            "headers": {"content-type": response.headers.get("content-type", "application/json")},
            "is_json": is_json,
            "body": body,
        }

    @staticmethod
    def _rebuild_response(stored: dict[str, Any], request: httpx.Request) -> httpx.Response:
        """Reconstruct an ``httpx.Response`` from a stored cassette entry."""
        headers = stored.get("headers", {})
        if stored.get("is_json", True):
            return httpx.Response(
                status_code=stored["status_code"],
                json=stored["body"],
                headers=headers,
                request=request,
            )
        return httpx.Response(
            status_code=stored["status_code"],
            text=stored["body"],
            headers=headers,
            request=request,
        )

    @staticmethod
    def _request_payload(request: httpx.Request, step_key: str) -> dict[str, Any]:
        """Build the audit/trace ``input`` payload describing the intercepted request."""
        raw = request.content
        body: Any = None
        if raw:
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                body = raw.decode("utf-8", errors="replace")
        return {"step_key": step_key, "path": request.url.path, "body": body}


class RecordingTransport(_RecordingCore, httpx.BaseTransport):
    """A sync ``httpx`` transport that records, replays, or passes through CF AI calls."""

    def __init__(
        self,
        run_id: str,
        mode: FlightMode | None = None,
        *,
        inner: httpx.BaseTransport | None = None,
    ) -> None:
        """Create a transport bound to one run.

        Args:
            run_id: UUID of the run being recorded/replayed.
            mode: Override for ``FLIGHT_MODE``; resolved from the env when ``None``.
            inner: Transport used to forward live calls; defaults to a real
                ``httpx.HTTPTransport`` (created lazily so replay never opens a
                socket).
        """
        self._init_recording(run_id, mode)
        self._inner: httpx.BaseTransport | None = inner

    @property
    def inner(self) -> httpx.BaseTransport:
        """The live-forwarding transport, created on first use."""
        if self._inner is None:
            self._inner = httpx.HTTPTransport()
        return self._inner

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Route one request according to the current mode."""
        if not is_cf_workers_ai_url(request.url):
            return self._forward(request)
        step_key = cassette.hash_step_key(cassette.normalize_request(request))
        if self.mode == "replay":
            return self._replay(request, step_key)
        if self.mode == "passthrough":
            return self._forward(request)
        return self._record(request, step_key)

    def _forward(self, request: httpx.Request) -> httpx.Response:
        """Forward a request to the live transport, counting it as a live call."""
        self.live_call_count += 1
        return self.inner.handle_request(request)

    def _record(self, request: httpx.Request, step_key: str) -> httpx.Response:
        """Forward, store the response + trace record, and write an audit record."""
        response = self._forward(request)
        response.read()
        stored = self._serialize_response(response)
        self._persist(request, step_key, stored)
        return self._rebuild_response(stored, request)

    def close(self) -> None:
        """Close + drop the live transport so the recorder can outlive a client.

        ``httpx.Client`` closes its transport on exit; resetting ``_inner`` lets the
        same recorder (and its audit chain) be reused across several short-lived
        clients — the next call lazily creates a fresh inner transport.
        """
        if self._inner is not None:
            self._inner.close()
            self._inner = None


class AsyncRecordingTransport(_RecordingCore, httpx.AsyncBaseTransport):
    """An async ``httpx`` transport that records, replays, or passes through CF AI calls.

    The async analogue of :class:`RecordingTransport`, for services whose LLM
    client is an ``httpx.AsyncClient`` (atlassian-remote's ``cf_ai_client``). Only
    the forward is awaited; the cassette/audit writes are the same synchronous,
    fast storage calls used by the sync transport.
    """

    def __init__(
        self,
        run_id: str,
        mode: FlightMode | None = None,
        *,
        inner: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Create an async transport bound to one run.

        Args:
            run_id: UUID of the run being recorded/replayed.
            mode: Override for ``FLIGHT_MODE``; resolved from the env when ``None``.
            inner: Async transport used to forward live calls; defaults to a real
                ``httpx.AsyncHTTPTransport`` (created lazily so replay never opens a
                socket).
        """
        self._init_recording(run_id, mode)
        self._inner: httpx.AsyncBaseTransport | None = inner

    @property
    def inner(self) -> httpx.AsyncBaseTransport:
        """The live-forwarding async transport, created on first use."""
        if self._inner is None:
            self._inner = httpx.AsyncHTTPTransport()
        return self._inner

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Route one request according to the current mode."""
        if not is_cf_workers_ai_url(request.url):
            return await self._forward(request)
        step_key = cassette.hash_step_key(cassette.normalize_request(request))
        if self.mode == "replay":
            return self._replay(request, step_key)
        if self.mode == "passthrough":
            return await self._forward(request)
        return await self._record(request, step_key)

    async def _forward(self, request: httpx.Request) -> httpx.Response:
        """Forward a request to the live async transport, counting it as a live call."""
        self.live_call_count += 1
        return await self.inner.handle_async_request(request)

    async def _record(self, request: httpx.Request, step_key: str) -> httpx.Response:
        """Forward, store the response + trace record, and write an audit record."""
        response = await self._forward(request)
        await response.aread()
        stored = self._serialize_response(response)
        self._persist(request, step_key, stored)
        return self._rebuild_response(stored, request)

    async def aclose(self) -> None:
        """Close + drop the live transport so the recorder can outlive a client.

        ``httpx.AsyncClient`` closes its transport on exit; resetting ``_inner``
        lets one recorder (and its audit chain) span several short-lived clients —
        the analyze flow makes embed + RCA calls through separate clients — by
        lazily recreating a fresh inner transport on the next call.
        """
        if self._inner is not None:
            await self._inner.aclose()
            self._inner = None
